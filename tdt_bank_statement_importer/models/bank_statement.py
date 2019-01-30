from base64 import b64decode
from datetime import datetime
import csv, io

from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError


class BankStatement(models.Model):
    _inherit = 'account.bank.statement'

    def csv_import(self):
        self.ensure_one()
        wiz = self.env['tdt.bank_statement_importer'].create({
            'statement_id': self.id,
        })
        return {
            'name': 'Import Bank Statement',
            'type': 'ir.actions.act_window',
            'target': 'new',
            'view_mode': 'form',
            'view_type': 'form',
            'res_model': wiz._name,
            'res_id': wiz.id,
        }


class BankStatementImporter(models.TransientModel):
    _name = 'tdt.bank_statement_importer'

    def _get_banks(self):
        return [
            ('fcib', 'FCIB (First Carribean International Bank)'),
            ('emirates_nbd', 'Emirates NBD'),
        ]

    csv = fields.Binary(
        string='CSV',
    )
    encoding = fields.Selection(
        selection=[
            ('UTF-8', 'UTF-8'),
            ('ISO-8859-1', 'ISO-8859-1'),
            ('ISO-8859-15', 'ISO-8859-15'),
            ('Windows-1252', 'Windows-1252'),
            ('CP850', 'CP850'),
            ('CP858', 'CP858'),
            ('CP859', 'CP859'),
            ('US-ASCII', 'US-ASCII'),
        ],
        string='Encoding',
        default='UTF-8',
        required=True,
    )
    delimiter = fields.Char(
        string='Delimiter',
        default=',',
        required=True,
    )
    statement_id = fields.Many2one(
        'account.bank.statement',
        required=True,
    )
    bank = fields.Selection(
        selection=_get_banks,
        string="Bank",
        default='fcib',
        required=True,
    )

    def _emirates_nbd_parse(self, stream):
        FIELDS = (
            'type', 'account', 'date', 'amount', 'op_type', 'op_name',
            'ref', 'ref_name', 'name', 'note', '_', 'date_mov', 'op_code',
        )
        CONV = {
            'date': lambda x: datetime.strptime(x, '%m/%d/%Y'),
            'amount': float,
            'date_mov': lambda x: datetime.strptime(x, '%d/%m/%Y'),
        }
        reader = csv.DictReader(stream, fieldnames=FIELDS)
        # Header
        ltype, account, date_begin, date_end, _, currency = reader.reader.__next__()
        if ltype != '1':
            raise ValidationError('Wrong file header format')
        date_begin = datetime.strptime(date_begin, '%d%m%Y')
        date_end = datetime.strptime(date_end, '%d%m%Y')
        # Normal lines
        for line in reader:
            if line['type'] != '2':
                raise ValidationError('Wrong format on line %d' % reader.line_num)
            for i in CONV:
                line[i] = CONV[i](line[i])
            if line['op_type'] == 'DR':
                line['amount'] *= -1
            name = ', '.join((
                line[i] for i in ('op_name', 'ref_name', 'name', 'note')
            ))
            self.env['account.bank.statement.line'].create({
                'statement_id': self.statement_id.id,
                'date': line['date'],
                'name': name,
                'amount': line['amount'],
                'ref': line['ref'],
            })

    def _fcib_parse(self, stream):
        def fcib_header(inp):
            ret = {}
            for line in csv.reader(inp):
                if line[0].isspace():
                    break
                key, val = line[0].split(':', 1)
                val = val.lstrip('\t -')
                ret[key.title().translate({32: None, 9: None})] = val
            return ret
        header = fcib_header(stream)
        ref = '%s %s' % (header['AccountName'], header['SpecifiedPeriod'])
        date_start, date_end = header['SpecifiedPeriod'].translate({
            40: None, 41: None, 32: None,
        }).split('-')
        lines = csv.DictReader(stream, delimiter=self.delimiter)
        balance_start = None
        balance_end = amount = 0
        for line in lines:
            balance_end = -float(line[' Running Balance'])
            amount = float(line[' Credit Amount']) or -float(line[' Debit Amount'])
            if balance_start is None:
                balance_start = balance_end
            self.env['account.bank.statement.line'].create({
                'statement_id': self.statement_id.id,
                'date': datetime.strptime(line['Date'], '%d/%m/%Y'),
                'name': line[' Description'],
                'amount': amount,
            })
        self.statement_id.balance_start = balance_start
        self.statement_id.balance_end_real = balance_end + amount

    def process(self):
        self.ensure_one()
        if not self.csv:
            raise UserError('No file selected')
        parsers = {
            'fcib': self._fcib_parse,
            'emirates_nbd': self._emirates_nbd_parse,
        }
        inp = io.StringIO(b64decode(self.csv).decode(self.encoding))
        return parsers[self.bank](inp)
