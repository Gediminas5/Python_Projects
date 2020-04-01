# -*- encoding: utf-8 -*-
###########################################################################
#
#    Copyright (C) 2009 Sandas. (http://www.sandas.eu) All Rights Reserved.
#
###########################################################################

from report import report_sxw
from datetime import datetime
from dateutil.relativedelta import relativedelta


class Parser(report_sxw.rml_parse):
    def __init__(self, cr, uid, name, context):
        if context is None:
            context = {}
        super(Parser, self).__init__(cr, uid, name, context=context)
        self.localcontext.update({
            'context': context,
            'get_products': self._get_products,
            'get_dates': self._get_dates,
        })
    
    def _get_products(self, data):
        cr = self.cr
        uid = self.uid
        context = self.localcontext['context']

        product_obj = self.pool.get('product.product')

        ctx = context.copy()
        ctx['filter_zero_qty'] = True
        ctx['location'] = data['form']['location_id']
        ctx['to_date'] = data['form']['date_to']

        res = []
        for product_id in product_obj.search(cr, uid, [], context=ctx):
            product = product_obj.read(cr, uid, product_id, ['default_code', 'name'], context=ctx)
            line = {
                "default_code": product['default_code'],
                "name": product['name'],
            }
            product_qty_by_date = {}
            for date in self._get_dates(data):
                ctx['to_date'] = date['date_t']
                if date['date_t'] in product_qty_by_date.keys():
                    product_qty = product_qty_by_date[date['date_t']]
                else:
                    product_qty = product_obj.read(
                        cr, uid, product_id, ['qty_available', 'virtual_available'], context=ctx
                    )
                    product_qty_by_date[date['date_t']] = product_qty
                if date['text_t'] == "Tikros atsargos":
                    line.update({('real', date['text_t'], date['date_t']): True,
                                 (date['text_t'], date['date_t']): product_qty['qty_available']
                                 })
                elif date['text_t'] == "Virtualus kiekis":
                    if product_qty['virtual_available'] >= 0.0:
                        line.update({('positive', date['text_t'], date['date_t']): True})
                    else:
                        line.update({('negative', date['text_t'], date['date_t']): True})
                    line.update({(date['text_t'], date['date_t']): product_qty['virtual_available']})
            res.append(line)
        return res

    def _get_dates(self, data):
        date_to_obj = datetime.strptime(data['form']['date_to'], '%Y-%m-%d')
        return [{
                'date_t': (date_to_obj + relativedelta(days=days)).strftime('%Y-%m-%d'),
                'text_t': (i % 2) == 0 and "Virtualus kiekis" or "Tikros atsargos"
                }
                for days in range(30) for i in range(2)]
