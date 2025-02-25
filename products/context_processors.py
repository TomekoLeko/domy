from .models import Cart

def cart_processor(request):
    context = {}
    
    if request.user.is_authenticated:
        # Get selected buyer from session
        selected_buyer_id = request.session.get('selected_buyer_id')
        
        if selected_buyer_id:
            # Get cart for the selected buyer
            cart = Cart.objects.filter(
                user=request.user,
                buyer_id=selected_buyer_id
            ).first()
        else:
            # For regular users, get their own cart
            cart = Cart.objects.filter(
                user=request.user,
                buyer=request.user
            ).first()
            
        if cart:
            context['cart'] = cart
            context['cart_count'] = cart.total_items
    
    return context 
