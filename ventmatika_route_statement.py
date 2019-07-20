# -*- encoding: utf-8 -*-
###########################################################################
#
#    Copyright (C) 2009 Sandas. (http://www.sandas.eu) All Rights Reserved.
#
###########################################################################

from report import report_sxw

# !Real Parser is in the file mrp_report.xml
class Parser(report_sxw.rml_parse):
    def __init__(self, cr, uid, name, context):
        if context is None:
            context = {}
        super(Parser, self).__init__(cr, uid, name, context=context)
        self.localcontext.update({
            'get_lines': self._get_lines,
            'context': context,
        })

    def _get_mrp_lines(self, object):

        cr = self.cr
        uid = self.uid
        context = self.localcontext['context']

        mpl_obj = self.pool.get('mrp.production.line')

        mpl_ids = mpl_obj.search(cr, uid, [
            ('production_id', '=', object.id),
        ], context=context)

        mpl_l_obj = mpl_obj.browse(cr, uid, mpl_ids, context=context)

        return mpl_l_obj

    def _get_lines(self, object):

        mpl_l_a_s_other_obj = self._get_a_s_other(object)

        res = []

        for mpl_l in mpl_l_a_s_other_obj:

            line = {
                "code": mpl_l.product_id and mpl_l.product_id.default_code or '',
                "name": mpl_l.name or '',
                "rack": mpl_l.product_id and mpl_l.product_id.loc_rack or '',
                "qty_required": "{:.3f}".format(mpl_l.one_product_qty * object.product_qty).replace(".", ",") or '0,000',
                "uom": mpl_l.product_id and mpl_l.product_id.uom_id and mpl_l.product_id.uom_id.name or '',
                "mrp_quantity": "{:.3f}".format(mpl_l.one_product_qty).replace(".", ",") or '0,000',
            }
            res.append(line)

        return res

    def _get_a_s_other(self, object):
        '''Mrp production lines arrange sequence like this: A, S, B, C, D, G.'''

        mpl_l_obj = self._get_mrp_lines(object)

        filtered_mpl_l_obj = sorted(mpl_l_obj, key=lambda x: x.product_id.loc_rack)

        rack_starts_with_a = []
        rack_starts_with_s = []
        rack_starts_with_other = []
        rack_with_no_letter = []

        for letter in filtered_mpl_l_obj:
            if letter.product_id.loc_rack:
                if letter.product_id.loc_rack.find("A") == 0:
                    rack_starts_with_a.append(letter)
                elif letter.product_id.loc_rack.find("S") == 0:
                    rack_starts_with_s.append(letter)
                else:
                    rack_starts_with_other.append(letter)
            else:
                rack_with_no_letter.append(letter)

        mpl_l_a_s_other_obj = rack_with_no_letter + rack_starts_with_a + rack_starts_with_s + rack_starts_with_other

        return mpl_l_a_s_other_obj

