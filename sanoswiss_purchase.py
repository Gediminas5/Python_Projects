# -*- encoding: utf-8 -*-
##############################################################################
#
# Copyright (c) 2008 Activity Solutions. (http://www.activity.lt) All Rights Reserved.
#
##############################################################################

import base64
from copy import deepcopy
from datetime import datetime, timedelta

import decimal_precision as dp
from osv import fields, osv
from tools.translate import _

from export_rules import PURCHASE_ORDER_DETAILS_HEADER, PURCHASE_ORDER_HEADER, FC_PURCHASE_ORDER_RESULT_HEADER


class working_hours(osv.osv):
    _name = 'working.hours'
    _description = 'Working hours'
    
    _columns = {
        'name': fields.char("Name", size=128, required=True),
    }


working_hours()


class purchase_order_required_doc(osv.osv):
    _name = 'purchase.order.required_doc'
    _description = 'Required document'
    
    _columns = {
        'name': fields.char("Name", size=128, required=True),
    }


purchase_order_required_doc()


class purchase_order(osv.osv):
    _inherit = 'purchase.order'
    
    def _amount_all(self, cr, uid, ids, field_name, arg, context):
        res = {}
        cur_obj=self.pool.get('res.currency')
        for order in self.browse(cr, uid, ids):
            res[order.id] = {
                'amount_untaxed': 0.0,
                'amount_tax': 0.0,
                'amount_total': 0.0,
            }
#Sandas+
            #val = val1 = 0.0
            val1 = 0.0
#Sandas-
            cur=order.pricelist_id.currency_id
#Sandas+
            tax_dict = {}
#Sandas-
            for line in order.order_line:
                val1 += line.price_subtotal
#Sandas+
                for t in line.taxes_id:
                    if t.id not in tax_dict.keys():
                        tax_dict[t.id] = 0.0
#Sandas-
#Sandas+
                #for c in self.pool.get('account.tax').compute(cr, uid, line.taxes_id, line.price_unit, line.product_qty, order.partner_address_id.id, line.product_id, order.partner_id, cur):
                for c in self.pool.get('account.tax').compute(cr, uid, line.taxes_id, (line.product_qty != 0.0) and (line.price_subtotal / line.product_qty) or 0.0, line.product_qty, order.partner_address_id.id, line.product_id, order.partner_id, cur):
#Sandas-
#Sandas+
#                        print "C:", c
#                    if c['rounding_method'] in ['each_line']:
#                        tax_dict[c['id']] += cur_obj.round(cr, uid, cur, c['amount'])
#                    else:
                        tax_dict[c['id']] += c['amount']
#                    val+= c['amount']
            for t_id in tax_dict.keys():
                res[order.id]['amount_tax'] += cur_obj.round(cr, uid, cur, tax_dict[t_id])
#            res[order.id]['amount_tax'] += cur_obj.round(cr, uid, cur, val)
#Sandas-
            res[order.id]['amount_untaxed']=cur_obj.round(cr, uid, cur, val1)
            res[order.id]['amount_total']=res[order.id]['amount_untaxed'] + res[order.id]['amount_tax']
        return res
    
    def _get_order(self, cr, uid, ids, context=None):
        result = {}
        for line in self.pool.get('purchase.order.line').browse(cr, uid, ids, context=context):
            result[line.order_id.id] = True
        return result.keys()
    
    _columns = {
        'delivery_address_id': fields.many2one('res.partner.address', "Delivery Address"),
        'delivery_date': fields.date("Delivery Date"),
        'working_hours_id': fields.many2one('working.hours', "Working Hours"),
        'required_doc_ids': fields.many2many(
            'purchase.order.required_doc', 'purchase_req_doc_rel',
            'purchase_id', 'req_doc_id', string="Required Documents"
        ),
        'received_from_wms_picking_datetime': fields.datetime('Received from WMS', readonly=True),
        'amount_untaxed': fields.function(_amount_all, method=True, digits_compute=dp.get_precision('Purchase Price'), string='Untaxed Amount',
            store={
                'purchase.order.line': (_get_order, None, 10),
            }, multi="sums"),
        'amount_tax': fields.function(_amount_all, method=True, digits_compute=dp.get_precision('Purchase Price'), string='Taxes',
            store={
                'purchase.order.line': (_get_order, None, 10),
            }, multi="sums"),
        'amount_total': fields.function(_amount_all, method=True, digits_compute=dp.get_precision('Purchase Price'), string='Total',
            store={
                'purchase.order.line': (_get_order, None, 10),
            }, multi="sums"),
        'received_in_parts': fields.boolean('Received in Parts')
#         'address_code': fields.char(Address Code),
#         'order_date_end': fields.char(Order Date End),
    }
    
# < -- FC priemimo uzsakymai 
    def import_file_from_wms_to_openerp_po(self, cr, uid, context=None):
        ir_log_obj = self.pool.get('ir.login')
        job_obj = self.pool.get('ir.job')
        files = ir_log_obj.get_files_from_equinox_ftp(cr, uid, file_name="SANOSWISS-FC*", context=context)
        for file_name in files:
            job_id = job_obj.register_job(
                cr, uid, _('Import from WMS to OpenERP PO (%s)') % file_name.split('/')[-1],
                1, context=context
            )
            try:
                file_str, file_data = ir_log_obj.read_file(cr, uid, {
                    '1': FC_PURCHASE_ORDER_RESULT_HEADER
                }, file_name, context=context)
                job_obj.update_job(cr, uid, job_id, {
                    'report_data': base64.encodestring(file_str),
                    'report_data_fname': file_name.split('/')[-1]
                }, context=context)
                self.create_purchase_order_line_for_fc(cr, uid, file_data, context=context)
                # fc_line_obj.reupload_purchase_orders(cr, uid, fc_line_ids, context=context)
                cr.commit()
                ir_log_obj.remove_file(cr, uid, file_name, context=context)
            except Exception, e:
                if job_id:
                    job_obj.job_exception(cr, uid, job_id, e, context=context)
                continue
            job_obj.job_done(cr, uid, job_id, context=context)

        return True
    
    def cron_import_file_from_wms_to_openerp_po(self, cr, uid, context=None):
        if context is None:
            context = {}
        self.import_file_from_wms_to_openerp_po(cr, uid, context=context)
        return True
# FC priemimo uzsakymai -->
    
# <---- PO priemimo uzsakymai
    def purchase_order_specification(self, cr, uid, ids, context=None):
        move_obj = self.pool.get('stock.move')
        product_obj = self.pool.get('product.product')
        res = [] 
        if not ids:
            return True
        for purchase_id in ids:
            purchase = self.browse(cr, uid, purchase_id, context=context)
            production_term = 0
            vals = {
                'header_type': '1',
                'name': purchase.name and purchase.name.encode('utf-8') or ' ',
                'origin': purchase.picking_ids and purchase.picking_ids[0].name.encode('utf-8') or ' ',
                'order_type': 'P',
                'ref': purchase.partner_id and str(purchase.partner_id.id) or '',
                'address_code': purchase.partner_address_id and str(purchase.partner_address_id.id) or '',
                'owner_code': 'SANOSWISS',
                'crlf': '\r\n',
            }
            res.append(vals)
            lines_grouped_by_product = {}
            for purchase_order_line in purchase.order_line:
                if not production_term:
                    production_term = product_obj.get_production_term(
                        cr, uid, purchase_order_line.product_id.id, context=context
                    )
                move_ids = move_obj.search(cr, uid, [
                    ('purchase_line_id', '=', purchase_order_line.id),
                    ('state', '=', 'done')
                ], context=context)
                qty = purchase_order_line.product_qty
                for move_id in move_ids:
                    move = move_obj.browse(cr, uid, move_id, context=context)
                    qty = qty - move.product_qty
                if purchase_order_line.product_id:
                    if purchase_order_line.product_id.id in lines_grouped_by_product:
                        vals_purchase_order_lines = lines_grouped_by_product[purchase_order_line.product_id.id]
                    else:
                        vals_purchase_order_lines = {
                            'header_type': '2',
                            'erp_id':
                                purchase_order_line.product_id and str(purchase_order_line.product_id.id) or ' ',
                            'quantity': '0',
                            'crlf': '\r\n',
                        }
                        lines_grouped_by_product[purchase_order_line.product_id.id] = vals_purchase_order_lines
                        res.append(vals_purchase_order_lines)
                    vals_purchase_order_lines['quantity'] = str(float(vals_purchase_order_lines['quantity']) + qty)
            approve_date = datetime.strptime(purchase.date_approve, '%Y-%m-%d')
            term_date = approve_date + timedelta(days=production_term*30)
            vals.update(order_date_end=term_date.strftime('%Y%m%d'))
        return res

    def filter_purchase_for_equinox_export(self, cr, uid, ids, context=None):
        purchase_to_export_ids = []
        skipped_purchase_ids = []
        for purchase_id in ids:
            purchase = self.browse(cr, uid, purchase_id, context=context)
            if purchase.warehouse_id and purchase.warehouse_id.skip_export_to_equinox_ftp:
                skipped_purchase_ids.append(purchase_id)
            else:
                purchase_to_export_ids.append(purchase_id)
        return purchase_to_export_ids, skipped_purchase_ids

    def add_purchase_order_to_ftp(self, cr, uid, ids, context=None):        
        ir_seq_obj = self.pool.get('ir.sequence')
        ir_log_obj = self.pool.get('ir.login')
        job_obj = self.pool.get('ir.job')
        job_id = job_obj.register_job(
            cr, uid, _('Purchase Order Export'), 
            1, context=context
        )
        seq_no = ''
        purchase_to_export_ids = []
        skipped_purchase_ids = []
        try:
            purchase_to_export_ids, skipped_purchase_ids = self.filter_purchase_for_equinox_export(
                cr, uid, ids, context=context
            )
            if purchase_to_export_ids:
                purchases = self.purchase_order_specification(cr, uid, ids, context=context)
                seq_no = ir_seq_obj.get(cr, uid, 'purchase_order_export')
                file_data = ir_log_obj.create_file(cr, uid, purchases, {
                    '2': PURCHASE_ORDER_DETAILS_HEADER,
                    '1': PURCHASE_ORDER_HEADER
                }, seq_no+'.txt', context=context)
                job_obj.update_job(cr, uid, job_id, {
                    'report_data': base64.encodestring(file_data),
                    'report_data_fname': seq_no+'.txt'
                }, context=context)
        except Exception, e:
            if job_id:
                job_obj.job_exception(cr, uid, job_id, e, context=context)
        ctx_note = context.copy()
        ctx_note['note'] = ''
        if purchase_to_export_ids:
            ctx_note['note'] += _('Exported %s purchases. File name: %s. Exported purchases ids: %s') % (
                str(len(purchase_to_export_ids)), seq_no, str(purchase_to_export_ids)
            )
        if skipped_purchase_ids:
            ctx_note['note'] += '\n' + _('Skipped %s purchases: %s. (Filtered out by warehouse configuration - "%s")') % (
                str(len(skipped_purchase_ids)), str(skipped_purchase_ids), _('Skip Export to Equinox')
            )
        job_obj.job_done(cr, uid, job_id, context=ctx_note)

        return True
    
    def action_picking_create(self, cr, uid, ids, context=None):

        pol_obj = self.pool.get('purchase.order.line')
        product_obj = self.pool.get('product.product')

        result = super(purchase_order, self).action_picking_create(
            cr, uid, ids, context=context
        )

        for id in ids:
            purchase = self.browse(cr, uid, id, context=context)
            for line in purchase.order_line:
                if line.product_id:
                    production_term = product_obj.get_production_term(
                        cr, uid, line.product_id.id, context=context
                    )
                    approve_date = datetime.strptime(purchase.date_approve, '%Y-%m-%d')
                    date_planned = approve_date + timedelta(days=production_term * 30)
                    pol_obj.write(cr, uid, [line.id], {
                        'date_planned': date_planned
                    }, context=context)

        self.add_purchase_order_to_ftp(cr, uid, ids, context=context)
        return result

    def create_purchase_order_line_for_fc(self, cr, uid, file_data, context=None):
        purchase_order_line_fc_obj = self.pool.get('purchase.order.line.fc')
        product_obj = self.pool.get('product.product')
        # pick_obj = self.pool.get('stock.picking')
        move_obj = self.pool.get('stock.move')
        purchase_obj = self.pool.get('purchase.order')
        purchase_line_obj = self.pool.get('purchase.order.line')

        all_fc_line_ids = []
        for fd in file_data:
            purchase_ids = purchase_obj.search(cr, uid, [
                ('name', '=', fd['picking_number']),
            ], context=context)
            if not purchase_ids:
                if fd['picking_number'].startswith('SVS'):
                    continue
                raise osv.except_osv(
                    _('Error'),
                    _('There are no purchases with number %s') % fd['picking_number']
                )

            product_id = int(fd['erp_id'])
            purchase_line_ids = purchase_line_obj.search(cr, uid, [
                ('order_id', 'in', purchase_ids),
                ('product_id', '=', product_id),
                ('product_qty', '=', fd['ordered_qty']),
            ], order='id desc', context=context) or purchase_line_obj.search(cr, uid, [
                ('order_id', 'in', purchase_ids),
                ('product_id', '=', product_id),
                ('product_qty', '=', fd['sent_qty']),
            ], order='id desc', context=context) or purchase_line_obj.search(cr, uid, [
                ('order_id', 'in', purchase_ids),
                ('product_id', '=', product_id),
            ], order='id desc', context=context)
            if not purchase_line_ids:
                raise osv.except_osv(
                    _('Error'),
                    _('There are no purchase lines with purchase number %s and product %s') % (
                        fd['picking_number'], product_obj.browse(cr, uid, product_id, context=context).name
                    )
                )
            move_ids = move_obj.search(cr, uid, [
                ('purchase_line_id', '=', purchase_line_ids[0]),
                ('state', 'not in', ['done', 'cancel']),
            ], order='id desc', context=context) or move_obj.search(cr, uid, [
                ('purchase_line_id', '=', purchase_line_ids[0]),
            ], order='id desc', context=context)

            if not move_ids:
                raise osv.except_osv(
                    _('Error'),
                    _('There are no moves for purchase order %s and product %s') % (
                        fd['picking_number'], product_obj.browse(cr, uid, product_id, context=context).name
                    )
                )

            purchase_order_line_id = purchase_line_ids[0]
            fc_line_ids = purchase_order_line_fc_obj.search(cr, uid, [
                ('name', '=', fd['svs_order']),
                ('purchase_order_line_id', '=', purchase_order_line_id),
                ('move_id', '=', move_ids[0]),
                ('product_qty', '=', fd['sent_qty'])
            ], context=context)
            if not fc_line_ids:
                fc_line_id = purchase_order_line_fc_obj.create(cr, uid, {
                    'name': fd['svs_order'],
                    'product_qty': fd['sent_qty'],
                    'purchase_order_line_id': purchase_order_line_id,
                    'tracking': fd['tracking_name'],
                    'move_id': move_ids[0],
                    'received_from_wms_datetime': fd['recieving_date'],
                    'valid_date': fd['valid_date']
                }, context=context)
            else:
                fc_line_id = fc_line_ids[0]
            all_fc_line_ids.append(fc_line_id)
            # purchase_order_line_fc_obj.process_receive_line(cr, uid, purchase_order_line_fc_ids, context=context)
        purchase_order_line_fc_obj.process_done_line(cr, uid, all_fc_line_ids, context=context)

        return all_fc_line_ids

        
purchase_order()


class purchase_order_line_fc(osv.osv):
    _name = 'purchase.order.line.fc'
    _description = 'Purchase Order Line FC'
    
    _columns = {
        'name': fields.char("Name", size=128, required=True),
        'purchase_order_line_id': fields.many2one(
            'purchase.order.line', 'Purchase Order Line', readonly=True
        ),
        'move_id': fields.many2one('stock.move', 'Stock Move', readonly=True),
        'product_qty': fields.float('Quantity', required=True),
        'tracking': fields.char('Tracking Lot', size=32, readonly=True),
        'received_from_wms_datetime': fields.datetime('Received from WMS', readonly=True),
        'valid_date': fields.date('Valid Date', readonly=True)
    }
    
    def reupload_purchase_orders(self, cr, uid, ids, context=None):
        po_obj = self.pool.get('purchase.order')
        purchase_ids = set()
        for id in ids:
            fc_line = self.browse(cr, uid, id, context=context)
            purchase_ids.add(fc_line.purchase_order_line_id.order_id.id)
        if purchase_ids:
            po_obj.add_purchase_order_to_ftp(cr, uid, list(purchase_ids), context=context)
            
        return True
    
    def process_receive_line(self, cr, uid, ids, context=None):
        move_obj = self.pool.get('stock.move')
#         purchase_obj = self.pool.get('purchase.order')
        for id in ids:
            purchase_order_line_fc = self.browse(cr, uid, id, context=context)
            if purchase_order_line_fc.move_id:
                continue
            move_ids = move_obj.search(cr, uid, [
                ('purchase_line_id', '=', purchase_order_line_fc.purchase_order_line_id.id),
                ('state', '!=', 'done'),
            ], context=context)
            for move_id in move_ids:
                move = move_obj.browse(cr, uid, move_id, context=context)
                self.write(cr, uid, [id], {
                    'move_id': move.id,
                }, context=context)
        return True

    def process_done_line(self, cr, uid, ids, context=None):
        if context is None:
            context = {}
        move_obj = self.pool.get('stock.move')
        picking_obj = self.pool.get('stock.picking')
        stock_track_obj = self.pool.get('stock.tracking')
        stock_move_track_obj = self.pool.get('stock.move.tracking')
        purchase_order_obj = self.pool.get('purchase.order')
        pickings = {}
        
        d = {
            'model': 'stock.picking',
            'report_type': 'pdf',
            'ids': [],
            'form': {'moves': []},
            'id': False
        }
        
        all_picking_ids = []
        for id in ids:
            purchase_order_line_fc = self.browse(cr, uid, id, context=context)
            if purchase_order_line_fc.move_id.state == 'done':
                continue
            picking_d = pickings.setdefault(purchase_order_line_fc.move_id.picking_id.id, deepcopy(d))
            if purchase_order_line_fc.received_from_wms_datetime \
                and purchase_order_line_fc.received_from_wms_datetime != \
                    purchase_order_line_fc.move_id.picking_id.received_from_wms_datetime:
                picking_obj.write(cr, uid, [purchase_order_line_fc.move_id.picking_id.id], {
                    'received_from_wms_datetime': purchase_order_line_fc.received_from_wms_datetime
                }, context=context)
                purchase_order_obj.write(cr, uid, [purchase_order_line_fc.purchase_order_line_id.order_id.id], {
                    'received_from_wms_picking_datetime': purchase_order_line_fc.received_from_wms_datetime
                }, context=context)

            tracking_ids = stock_track_obj.search(cr, uid, [
                ('name', '=', purchase_order_line_fc.tracking)
            ], context=context)
            if not tracking_ids:
                stock_track_id = stock_track_obj.create(cr, uid, {
                    'name': purchase_order_line_fc.tracking,
                    'valid_date': purchase_order_line_fc.valid_date
                }, context=context)
            else:
                stock_track_id = tracking_ids[0]

            stock_move_track_ids = stock_move_track_obj.search(cr, uid, [
                ('move_id', '=', purchase_order_line_fc.move_id.id),
                ('tracking_id', '=', stock_track_id)
            ], context=context)
            quantity_with_tracking = sum([
                stock_move_track.quantity for stock_move_track
                in stock_move_track_obj.browse(cr, uid, stock_move_track_ids, context=context)
            ])
            if quantity_with_tracking < purchase_order_line_fc.product_qty:
                stock_move_track_obj.create(cr, uid, {
                    'tracking_id': stock_track_id,
                    'quantity': purchase_order_line_fc.product_qty - quantity_with_tracking,
                    'move_id': purchase_order_line_fc.move_id.id
                })
            
            move_ids = [purchase_order_line_fc.move_id.id]
            picking_id = purchase_order_line_fc.move_id.picking_id.id
            
            for move_id in move_ids:
                if 'move'+str(move_id) not in picking_d['form']:
                    picking_d['form']['move' + str(move_id)] = 0
                    picking_d['form']['moves'].append(purchase_order_line_fc.move_id.id)
                picking_d['form']['move'+str(move_id)] += purchase_order_line_fc.product_qty
                picking_d['id'] = picking_id
                picking_all_ids = [picking_id]
                all_picking_ids += picking_all_ids
            picking_d['ids'] = [purchase_order_line_fc.move_id.picking_id.id]
            
        for picking_dict in pickings.values():
            result = picking_obj.do_split(cr, uid, picking_dict, context=context)

            if result['new_picking']:
                for id in ids:
                    purchase_order_line_fc = self.browse(cr, uid, id, context=context)
                    move_ids = move_obj.search(cr, uid, [
                        ('product_id', '=', purchase_order_line_fc.move_id.product_id.id),
                        ('picking_id', '=', result['new_picking'])
                    ], context=context)

                    for move_id in move_ids:
                        self.write(cr, uid, [purchase_order_line_fc.id], {
                            'move_id': move_id,
                        }, context=context)
        return True

    
purchase_order_line_fc()


class purchase_order_line(osv.osv):
    _inherit = 'purchase.order.line'
    
    _columns = {
        'shelf_life_id': fields.many2one('product.shelf_life', "Shelf Life"),
        'product_qty': fields.float('Quantity', required=True, digits_compute=dp.get_precision('Purchase Quantity')),
        'price_unit': fields.float('Unit Price', required=True, digits_compute=dp.get_precision('Purchase Price')),
    }
    
    def product_id_change(self, cr, uid, ids, pricelist, product, qty, uom,
            partner_id, date_order=False, fiscal_position=False, date_planned=False,
            name=False, price_unit=False, notes=False
        ):
        
        product_obj = self.pool.get('product.product')
        
        res = super(purchase_order_line, self).product_id_change(
            cr, uid, ids, pricelist, product, qty, uom, partner_id,
            date_order=date_order, fiscal_position=fiscal_position,
            date_planned=date_planned, name=name, price_unit=price_unit, notes=notes
        )
        
        if not res.get('value', False):
            res['value'] = {}
            
        if product:
            product_read = product_obj.read(cr, uid, product, [
                'shelf_life_id'
            ])
            if product_read['shelf_life_id']:
                res['value']['shelf_life_id'] = product_read['shelf_life_id'][0]
        
        return res

purchase_order_line()


class purchase_coefficients_report(osv.osv):
    _name = 'purchase.coefficients.report'
    _description = 'Purchase Coefficients Report'

    _columns = {
        'partner_id': fields.many2one('res.partner', "Client", required=True),
        'product_country_codes': fields.related('product_id', 'product_country_codes',
           type='char', size=64,
           string="Country Codes", readonly=True),
        'coefficient': fields.integer("Coefficient"),
        'product_id': fields.many2one('product.product', "Product", required=True),
        'product_code': fields.related('product_id', 'default_code',
            type="char", size=64,
            string="Product Code", readonly=True),
        'sale_price': fields.float("Sale Price", digits=(16, 2), readonly=True),
        'date_from': fields.date('Date From', required=True),
        'date_to': fields.date('Date To'),
        'profitability': fields.float("Profitability", digits=(16, 2), readonly=True),
        'main_line': fields.boolean("Relevant", readonly=True)
    }

    def write(self, cr, uid, ids, vals, context=None):
        res = super(purchase_coefficients_report, self).write(cr, uid, ids, vals, context=context)
        if {'product_id', 'partner_id', 'date_from'} & set(vals.keys()):
            self.update_pricelist_price_and_profitability(cr, uid, ids, context=context)
            self.filtered_by_product_and_supplier(cr, uid, ids, context=context)
        return res

    def create(self, cr, uid, vals, context=None):
        res = super(purchase_coefficients_report, self).create(cr, uid, vals, context=context)
        self.update_pricelist_price_and_profitability(cr, uid, [res], context=context)
        self.filtered_by_product_and_supplier(cr, uid, [res], context=context)
        return res

    def update_pricelist_price_and_profitability(self, cr, uid, ids, context=None):
        for id in ids:
            prod_obj = self.browse(cr, uid, id, context=context)
            if not prod_obj.product_id:
                continue
            if not prod_obj.partner_id.property_product_pricelist:
                continue
            pricelist_id = prod_obj.partner_id.property_product_pricelist.id
            qty = 1
            sale_price = self.pool.get('product.pricelist').price_get(cr, uid, [pricelist_id], prod_obj.product_id.id, qty,
                                partner=prod_obj.partner_id.id, context=context)[pricelist_id]
            profitability = self.get_profitability(cr, uid, prod_obj, sale_price, context=None)
            self.write(cr, uid, [id], {'sale_price': sale_price, 'profitability': profitability}, context=context)
        return True

    def get_profitability(self, cr, uid, prod_obj, price, context=None):

        stock_planning_obj = self.pool.get('stock.planning.report')

        stock_planning_unit_price_id = stock_planning_obj.search(cr, uid, [
            ('product_id', '=', prod_obj.product_id.id),
            ('main_line', '=', True),
        ], limit=1, context=context)

        if stock_planning_unit_price_id:
            stock_report_obj = stock_planning_obj.browse(cr, uid, stock_planning_unit_price_id[0], context=context)
            discount = price * (100 - prod_obj.coefficient)
            profitability = discount > 0 and (discount - stock_report_obj.unit_price) / discount or 0.0
        else:
            profitability = 0.0

        return profitability

    def filtered_by_product_and_supplier(self, cr, uid, ids, context=None):
        for id in ids:
            prod_obj = self.browse(cr, uid, id, context=context)
            same_line_ids = self.search(cr, uid, [
                ('product_id', '=', prod_obj.product_id.id),
                ('partner_id', '=', prod_obj.partner_id.id),
            ], order='date_from desc', context=context)
            self.write(cr, uid, same_line_ids[0], {'main_line': True}, context=context)
            self.write(cr, uid, same_line_ids[1:], {'main_line': False}, context=context)
        return True


purchase_coefficients_report()



