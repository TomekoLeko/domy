from .models import Cart
from .carts_views import determine_contribution_usage_old

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
                temporary_array, contribution_usage_array = determine_contribution_usage_old(selected_buyer_id)
                context['temporary_array'] = temporary_array or []
                context['contribution_usage_array'] = contribution_usage_array or []
                
                # Calculate the total contribution amount
                if contribution_usage_array:
                    total_contribution = sum(float(item['price']) for item in contribution_usage_array)
                    context['total_contribution'] = round(total_contribution, 2)
                else:
                    context['total_contribution'] = 0
                
                # Get the buyer's remaining contribution limit
                try:
                    from finance.models import MonthlyContributionUsage
                    buyer = cart.buyer
                    monthly_usage = MonthlyContributionUsage.objects.filter(
                        profile__user=buyer
                    ).order_by('-year', '-month').first()
                    
                    if monthly_usage:
                        context['remaining_limit'] = float(monthly_usage.remaining_limit)
                        
                        # Calculate how much of the limit will be used
                        context['contribution_usage_sum'] = context['total_contribution']
                        
                        # Calculate how much will remain after this order
                        context['remaining_after_order'] = context['remaining_limit'] - context['contribution_usage_sum']
                        
                        # Calculate percentage for progress bar
                        if context['remaining_limit'] > 0:
                            percentage = (context['contribution_usage_sum'] / context['remaining_limit']) * 100
                            context['contribution_percentage'] = min(percentage, 100)  # Cap at 100%
                        else:
                            context['contribution_percentage'] = 0
                        
                        # Calculate the remaining cost after deducting contribution
                        total_cart_cost = float(cart.total_cost)
                        context['remaining_cost'] = max(0, total_cart_cost - context['contribution_usage_sum'])
                except Exception:
                    # If there's any error, set defaults
                    context['remaining_limit'] = 0
                    context['contribution_usage_sum'] = 0
                    context['remaining_after_order'] = 0
                    context['contribution_percentage'] = 0
                    context['remaining_cost'] = float(cart.total_cost) if cart else 0
            except Cart.DoesNotExist:
                pass
    
    return context 
