    def get_all_product_ids(self, cr, uid, product_id, context=None):
        """Old products for average_usage calculation (for this formula all products must be included)"""
        prod_obj = self.pool.get('product.product')

        all_product_ids = []

        all_product_ids.append(product_id)

        old_product = prod_obj.read(cr, uid, product_id, [
            'old_product_id'
        ], context=context)

        old_product_id = old_product['old_product_id'] and old_product['old_product_id'][0] or False

        all_products_in = False

        if old_product_id:
            if not product_id == old_product_id:
                while not all_products_in:
                    if old_product_id not in all_product_ids:
                        all_product_ids.append(old_product_id)
                        old_product_obj = prod_obj.browse(
                            cr, uid, old_product_id, context=context
                        )
                        new_old_product_id = old_product_obj.old_product_id.id
                        old_product_id = new_old_product_id and new_old_product_id or old_product_id
                    else:
                        all_products_in = True

        return all_product_ids
