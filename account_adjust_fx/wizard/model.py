# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from datetime import datetime
from odoo.exceptions import RedirectWarning, UserError, ValidationError


class AccountMoveAdjustfx(models.TransientModel):
    _name = 'account.move.adjustfx'

    date_from = fields.Date(string='From Date')
    date_to = fields.Date(string='To Date')
    journal_ids = fields.Many2many('account.journal', 'adjustfx_journal_rel')
    company_id = fields.Many2one('res.company', 'Company', required=True, default=lambda self: self.env.user.company_id.id)
    state = fields.Selection([('draft', 'Unposted'), ('posted', 'Posted')], string='Status', default=False)

    @api.multi
    def action_apply(self, cancel_backorder=False):
        domain = [('company_id', '=', self.company_id.id)]
        journal_domain = [('update_posted', '=', False)]
        if self.date_from:
            domain += [('date', '>=', self.date_from)]
        if self.date_to:
            domain += [('date', '<=', self.date_to)]
        if self.state:
            domain += [('state', '=', self.state)]        
        if len(self.journal_ids) > 0:
            journal = [journal.id for journal in self.journal_ids]
            domain += [('journal_id', 'in', journal)]
            journal_domain += [('id', 'in', journal)]
    
        restricted_journal_ids = self.env['account.journal'].search(journal_domain)
        if len(restricted_journal_ids) > 0:
            jounal_name_list = [restricted_journal.name for restricted_journal in restricted_journal_ids]
            raise UserError(_("You cannot modify a posted entry of this following journal %s. First you should set the journal to allow cancelling entries. ") % (jounal_name_list))

        for account_move in self.env['account.move'].search(domain):
            state = account_move.state
            total_debit = 0
            total_credit = 0
            if state == 'posted':account_move.button_cancel()
            for line in account_move.line_ids:
                debit = 0
                credit = 0
                company_currency_id = line.account_id.company_id.currency_id
                amount = line.amount_currency
                if line.currency_id and company_currency_id and line.currency_id != company_currency_id:
                    amount = line.currency_id._convert(amount, company_currency_id, line.company_id, line.date or fields.Date.today())
                    debit = amount > 0 and amount or 0.0
                    credit = amount < 0 and -amount or 0.0   
                    self.env.cr.execute("update account_move_line set debit = %s,credit = %s where id = %s" % (debit,credit,line.id))
                    total_debit += debit
                    total_credit += credit
            if total_debit != total_credit:raise UserError(_("Cannot create unbalanced journal entry of %s. ") % (account_move.name))
            self.env.cr.execute("update account_move set amount = %s where id = %s" % (total_debit,account_move.id))
#            account_move.line_ids._onchange_amount_currency()
            if state == 'posted':account_move.post()
        return {'type': 'ir.actions.client', 'tag': 'reload',}



# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
