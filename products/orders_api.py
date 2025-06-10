def get_order_with_items(order_id):

    print("get_order_with_items aaaa bbbb cccc")

    from products.models import Order, OrderItem
    
    try:
        # Get the order with its related buyer
        order = Order.objects.select_related('buyer', 'buyer__profile').get(id=order_id)
        
        # Get all order items with their related products
        order_items = OrderItem.objects.filter(order=order).select_related('product')
        
        # Get buyer name from profile or username
        buyer_name = order.buyer.profile.name if order.buyer and hasattr(order.buyer, 'profile') and order.buyer.profile.name else order.buyer.username if order.buyer else 'Unknown'
        
        # Create a dictionary with order and items information
        order_data = {
            'id': order.id,
            'buyer_name': buyer_name,
            'buyer_id': order.buyer.id if order.buyer else 'Unknown',
            'created_at': order.created_at.strftime('%Y-%m-%d %H:%M') if order.created_at else 'Unknown',
            'status': order.status,
            'total_cost': str(order.total_cost),
            'unpaid_amount': str(order.unpaid_amount),
            'items': []
        }


        print("order_data", order_data)
        
        # Add items to the order data
        for item in order_items:
            item_data = {
                'id': item.id,
                'product_id': item.product.id,
                'product_name': item.product.name,
                'quantity': item.quantity,
                'price': str(item.price),
                'subtotal': str(item.price * item.quantity),
                'stock_reductions': [],
                'payments': []
            }
            
            # Get stock reductions if they exist
            if hasattr(item, 'stock_reductions'):
                for reduction in item.stock_reductions.all():
                    item_data['stock_reductions'].append({
                        'id': reduction.id,
                        'quantity': reduction.quantity,
                        'stock_type': reduction.stock_type
                    })
            
            # Get payments if they exist
            if hasattr(item, 'payments'):
                for payment in item.payments.all():
                    item_data['payments'].append({
                        'id': payment.id,
                        'amount': str(payment.amount)
                    })
            
            order_data['items'].append(item_data)
        
        return order_data
    except Order.DoesNotExist:
        return None

