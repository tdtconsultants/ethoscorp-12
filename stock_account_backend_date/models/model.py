# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from odoo.exceptions import except_orm, Warning, RedirectWarning

class Picking(models.Model):
    _inherit = "stock.picking"

    @api.one
    def _set_scheduled_date(self):
        super(Picking, self)._set_scheduled_date()
        if self.set_effective_date:
            for move in self.move_lines:
                for move_line in move.move_line_ids:move_line.date = self.scheduled_date
                

    set_effective_date = fields.Boolean(string='Set Scheduled Date as Effective Date', default=True, states={'done': [('readonly', True)], 'cancel': [('readonly', True)]})

    @api.multi
    def action_done(self):
        super(Picking, self).action_done()
        if self.set_effective_date:
            self.write({'date_done': self.scheduled_date})
            for move in self.move_lines:
                for move_line in move.move_line_ids:move_line.date = self.scheduled_date
                
                

class StockMove(models.Model):
    _inherit = "stock.move"

    def _create_account_move_line(self, credit_account_id, debit_account_id, journal_id):
        self.ensure_one()
        AccountMove = self.env['account.move']
        quantity = self.env.context.get('forced_quantity', self.product_qty)
        quantity = quantity if self._is_in() else -1 * quantity
        ref = self.picking_id.name
        date = False
        if self.picking_id and self.picking_id.scheduled_date and self.picking_id.set_effective_date:date = self.picking_id.scheduled_date
        if self.env.context.get('force_valuation_amount'):
            if self.env.context.get('forced_quantity') == 0:
                ref = 'Revaluation of %s (negative inventory)' % ref
            elif self.env.context.get('forced_quantity') is not None:
                ref = 'Correction of %s (modification of past move)' % ref
        move_lines = self.with_context(forced_ref=ref)._prepare_account_move_line(quantity, abs(self.value), credit_account_id, debit_account_id)
        if move_lines:
            if not date:date = self._context.get('force_period_date', fields.Date.context_today(self))
            new_account_move = AccountMove.sudo().create({
                'journal_id': journal_id,
                'line_ids': move_lines,
                'date': date,
                'ref': ref,
                'stock_move_id': self.id,
            })
            new_account_move.line_ids._onchange_amount_currency()
            new_account_move.post()





     
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
