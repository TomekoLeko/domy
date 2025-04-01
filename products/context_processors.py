from .models import Cart
from .carts_views import determine_contribution_usage

def cart_processor(request):
    """
    Context processor for cart-related data.
    Makes cart data and expanded items array available in all templates.
    """
    context = {}
    
    if request.user.is_authenticated:
        selected_buyer_id = request.session.get('selected_buyer_id')
        if selected_buyer_id:
            # Get the cart
            try:
                cart = Cart.objects.get(user=request.user, buyer_id=selected_buyer_id)
                context['cart'] = cart
                
                # Generate the expanded cart items array
                temporary_array, contribution_usage_array = determine_contribution_usage(selected_buyer_id)
                context['temporary_array'] = temporary_array or []
                context['contribution_usage_array'] = contribution_usage_array or []
                
                # Calculate the total contribution amount
                if contribution_usage_array:
                    total_contribution = sum(float(item['price']) for item in contribution_usage_array)
                    context['total_contribution'] = round(total_contribution, 2)
                else:
                    context['total_contribution'] = 0
            except Cart.DoesNotExist:
                pass
    
    return context 
