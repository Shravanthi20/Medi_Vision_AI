from datetime import datetime, timedelta, date as date_type, timezone
from sqlalchemy import func, desc, case
import logging
from .extensions import db
from .models.sales import SalesBill, SalesBillItem
from .models.core import Item, Customer

logger = logging.getLogger(__name__)
from .models.inventory import StockBatch
from .models.ai import CustomerPurchasePattern

def calculate_linear_regression(data):
    """
    Simple linear regression: y = mx + c
    data: list of (x, y) tuples where x is the day index and y is the sales value
    Returns: m, c
    """
    n = len(data)
    if n < 2:
        return 0, 0
    
    sum_x = sum(x for x, y in data)
    sum_y = sum(y for x, y in data)
    sum_xx = sum(x * x for x, y in data)
    sum_xy = sum(x * y for x, y in data)
    
    numerator_m = (n * sum_xy) - (sum_x * sum_y)
    denominator_m = (n * sum_xx) - (sum_x * sum_x)
    
    if denominator_m == 0:
        return 0, 0
        
    m = numerator_m / denominator_m
    c = (sum_y - (m * sum_x)) / n
    
    return m, c

def get_sales_forecast(days_back=30, forecast_days=7):
    """
    Forecast sales for the next few days based on history.
    """
    start_date = datetime.now(timezone.utc).date() - timedelta(days=days_back)
    
    # Get daily sales totals
    daily_sales = db.session.query(
        SalesBill.bill_date,
        func.sum(SalesBill.net_amount).label('total')
    ).filter(
        SalesBill.bill_date >= start_date,
        SalesBill.is_cancelled == False
    ).group_by(SalesBill.bill_date).order_by(SalesBill.bill_date).all()
    
    if not daily_sales:
        return {
            "forecast": [], 
            "trend": "stable", 
            "growth_rate": 0, 
            "historical": []
        }
        
    # Prepare data for regression
    min_date = daily_sales[0][0]
    data = []
    for d, total in daily_sales:
        x = (d - min_date).days
        data.append((x, float(total)))
        
    m, c = calculate_linear_regression(data)
    
    forecast = []
    last_day_index = data[-1][0] if data else 0
    
    for i in range(1, forecast_days + 1):
        x_future = last_day_index + i
        y_future = max(0, m * x_future + c)
        date_future = min_date + timedelta(days=x_future)
        forecast.append({
            "date": date_future.isoformat(),
            "predicted_sales": round(y_future, 2)
        })
        
    trend = "up" if m > 0.1 else "down" if m < -0.1 else "stable"
    
    return {
        "forecast": forecast,
        "trend": trend,
        "growth_rate": round(m, 4),
        "historical": [{"date": d.isoformat(), "total": float(t)} for d, t in daily_sales]
    }

def get_top_moving_items(limit=10, days_back=30):
    """
    Find items with the highest sales volume (Frequently Moving).
    """
    start_date = datetime.now(timezone.utc).date() - timedelta(days=days_back)
    
    top_items = db.session.query(
        SalesBillItem.item_id,
        Item.item_name,
        func.sum(SalesBillItem.qty_sold).label('total_qty')
    ).join(SalesBill, SalesBillItem.bill_id == SalesBill.bill_id).join(Item, SalesBillItem.item_id == Item.item_id).filter(
        SalesBill.bill_date >= start_date,
        SalesBill.is_cancelled == False
    ).group_by(SalesBillItem.item_id, Item.item_name).order_by(desc('total_qty')).limit(limit).all()
    
    return [
        {"item_id": item_id, "name": item_name, "quantity": int(total_qty)}
        for item_id, item_name, total_qty in top_items
    ]

def get_market_basket_analysis(limit=5):
    """
    Identify items frequently bought together (Affinity).
    """
    recent_bill_ids = db.session.query(SalesBill.bill_id).order_by(desc(SalesBill.created_at)).limit(500).subquery()
    
    from sqlalchemy.orm import aliased
    i1 = aliased(SalesBillItem)
    i2 = aliased(SalesBillItem)
    
    pairs = db.session.query(
        i1.item_id,
        i2.item_id,
        func.count('*').label('frequency')
    ).join(i2, i1.bill_id == i2.bill_id).filter(
        i1.item_id < i2.item_id,
        i1.bill_id.in_(recent_bill_ids)
    ).group_by(i1.item_id, i2.item_id).order_by(desc('frequency')).limit(limit).all()
    
    result = []
    for id1, id2, freq in pairs:
        item1 = db.session.query(Item.item_name).filter_by(item_id=id1).first()
        item2 = db.session.query(Item.item_name).filter_by(item_id=id2).first()
        result.append({
            "item1": item1[0] if item1 else id1,
            "item2": item2[0] if item2 else id2,
            "frequency": int(freq)
        })
        
    return result

def get_churn_risk_customers(days_threshold=60, min_total_spend=500):
    """
    Find customers who used to buy a lot but haven't visited in a while.
    """
    threshold_date = datetime.now(timezone.utc).date() - timedelta(days=days_threshold)
    
    customer_stats = db.session.query(
        SalesBill.customer_id,
        func.max(SalesBill.bill_date).label('last_visit'),
        func.sum(SalesBill.net_amount).label('total_spend')
    ).filter(
        SalesBill.customer_id != None,
        SalesBill.is_cancelled == False
    ).group_by(SalesBill.customer_id).subquery()
    
    churn_risk = db.session.query(
        Customer.customer_name,
        Customer.phone,
        customer_stats.c.last_visit,
        customer_stats.c.total_spend
    ).join(customer_stats, Customer.customer_id == customer_stats.c.customer_id).filter(
        customer_stats.c.last_visit < threshold_date,
        customer_stats.c.total_spend >= min_total_spend
    ).order_by(desc(customer_stats.c.total_spend)).limit(10).all()
    
    return [
        {
            "name": name,
            "phone": phone,
            "last_visit": last_visit.isoformat(),
            "total_spend": float(total_spend),
            "days_since_last_visit": (datetime.now(timezone.utc).date() - last_visit).days
        }
        for name, phone, last_visit, total_spend in churn_risk
    ]

def get_customer_lifetime_value(days_back=180):
    """
    Cluster customers using RFM (Recency, Frequency, Monetary) parameters.
    Segments: Champions, Loyal Refillers, At-Risk.
    """
    start_date = datetime.now(timezone.utc).date() - timedelta(days=days_back)
    
    # Query aggregated stats per customer
    stats = db.session.query(
        SalesBill.customer_id,
        Customer.customer_name,
        Customer.phone,
        func.count(SalesBill.bill_id).label('frequency'),
        func.sum(SalesBill.net_amount).label('monetary'),
        func.max(SalesBill.bill_date).label('last_visit')
    ).join(Customer, SalesBill.customer_id == Customer.customer_id).filter(
        SalesBill.customer_id != None,
        SalesBill.is_cancelled == False,
        SalesBill.bill_date >= start_date
    ).group_by(SalesBill.customer_id, Customer.customer_name, Customer.phone).all()
    
    segments = {
        "champions": {"name": "Champions", "count": 0, "total_spend": 0.0, "customers": [], "color": "#3b82f6", "desc": "Bought recently, buy often, and spend the most"},
        "loyal": {"name": "Loyal Refillers", "count": 0, "total_spend": 0.0, "customers": [], "color": "#22c55e", "desc": "High purchase frequency for chronic refills"},
        "at_risk": {"name": "At-Risk VIPs", "count": 0, "total_spend": 0.0, "customers": [], "color": "#f5a623", "desc": "High spenders who haven't visited recently"},
        "promising": {"name": "Promising / Walk-ins", "count": 0, "total_spend": 0.0, "customers": [], "color": "#a78bfa", "desc": "Recent shoppers or lower frequency buyers"}
    }
    
    today = datetime.now(timezone.utc).date()
    
    for cid, cname, phone, freq, mon, last_visit in stats:
        mon_val = float(mon or 0)
        recency = (today - last_visit).days if last_visit else 0
        
        # Determine segment
        if recency <= 30 and freq >= 8 and mon_val >= 5000:
            key = "champions"
        elif freq >= 4:
            key = "loyal"
        elif recency > 60 and mon_val >= 500:
            key = "at_risk"
        else:
            key = "promising"
            
        seg = segments[key]
        seg["count"] += 1
        seg["total_spend"] += mon_val
        seg["customers"].append({"name": cname, "phone": phone or "-", "spend": round(mon_val, 2), "recency": recency, "freq": freq})
            
    # Format return list
    result = []
    for k, v in segments.items():
        avg_spend = round(v["total_spend"] / v["count"], 2) if v["count"] > 0 else 0.0
        v["customers"].sort(key=lambda x: x["spend"], reverse=True)
        result.append({
            "id": k,
            "name": v["name"],
            "count": v["count"],
            "avg_spend": avg_spend,
            "total_spend": round(v["total_spend"], 2),
            "sample_customers": v["customers"][:5],
            "all_customers": v["customers"],
            "color": v["color"],
            "desc": v["desc"]
        })
        
    return result

def get_dynamic_stockout_risk(days_back=30):
    """
    Calculate real-time daily consumption velocity per item to predict remaining days of supply.
    """
    start_date = datetime.now(timezone.utc).date() - timedelta(days=days_back)
    
    # Calculate quantity sold per item over the period
    sales_velocity = db.session.query(
        SalesBillItem.item_id,
        func.sum(SalesBillItem.qty_sold).label('total_sold')
    ).join(SalesBill, SalesBillItem.bill_id == SalesBill.bill_id).filter(
        SalesBill.bill_date >= start_date,
        SalesBill.is_cancelled == False
    ).group_by(SalesBillItem.item_id).all()
    
    velocity_map = {item_id: float(sold or 0) / days_back for item_id, sold in sales_velocity}
    
    # Query items to get stock and compute stockout risk
    items = Item.query.filter_by(is_active=True).all()
    
    result = []
    for item in items:
        total_stock = db.session.query(func.coalesce(func.sum(StockBatch.current_qty), 0)).filter_by(item_id=item.item_id).scalar()
        stock = int(total_stock)
        
        # Base fallback velocity if no sales recorded recently
        vel = velocity_map.get(item.item_id, 0.1)
        if vel <= 0:
            vel = 0.1
            
        days_remaining = int(round(stock / vel))
        
        # Filter for items that have low days remaining or critical stock
        if days_remaining <= 25 or stock <= 15:
            if days_remaining <= 5 or stock == 0:
                risk = "CRITICAL"
                color = "#ef4444"
            elif days_remaining <= 12:
                risk = "HIGH"
                color = "#f5a623"
            else:
                risk = "MODERATE"
                color = "#3b82f6"
                
            result.append({
                "item_id": item.item_id,
                "name": item.item_name,
                "stock": stock,
                "daily_velocity": round(vel, 2),
                "days_remaining": days_remaining,
                "risk_level": risk,
                "color": color
            })
            
    # Sort by days remaining ascending
    result.sort(key=lambda x: x["days_remaining"])
    return result[:15]

def update_customer_purchase_pattern(customer_id, item_id, quantity_purchased, is_chronic=False):
    """
    Update customer purchase pattern when a bill is saved.
    
    Args:
        customer_id: ID of the customer who made the purchase
        item_id: ID of the item purchased
        quantity_purchased: Quantity of the item in this transaction
    """
    if not customer_id or not item_id:
        return
    
    try:
        today = date_type.today()
        pattern = CustomerPurchasePattern.query.filter_by(
            customer_id=customer_id,
            item_id=item_id
        ).first()
        
        if pattern:
            # Calculate interval if we have a previous purchase date
            if pattern.last_purchased_date:
                days_since_last = (today - pattern.last_purchased_date).days
                if days_since_last > 5: # Ignore very frequent small purchases
                    # Simple moving average for refill interval
                    if not hasattr(pattern, '_temp_interval'): # Logic to estimate interval
                        interval = days_since_last
                    else:
                        interval = (pattern._temp_interval + days_since_last) / 2
            
            pattern.purchase_count += 1
            pattern.total_quantity += quantity_purchased
            pattern.avg_quantity = pattern.total_quantity / pattern.purchase_count
            pattern.last_purchased_date = today
            
            # Estimate next refill date
            # Logic: If they bought 30 units, assume it lasts 30 days unless history says otherwise
            days_to_next = int(quantity_purchased) # Default: 1 per day
            pattern.next_expected_date = today + timedelta(days=days_to_next)
            if is_chronic:
                pattern.is_chronic = True
            
        else:
            pattern = CustomerPurchasePattern(
                customer_id=customer_id,
                item_id=item_id,
                purchase_count=1,
                total_quantity=quantity_purchased,
                avg_quantity=float(quantity_purchased),
                last_purchased_date=today,
                next_expected_date=today + timedelta(days=int(quantity_purchased)),
                is_chronic=is_chronic
            )
            db.session.add(pattern)
        
        db.session.flush()
    except Exception as e:
        logger.error("Error updating purchase pattern: %s", e)


def get_personalized_suggestions(customer_id, limit=10, days_back=90, exclude_recent_days=30):
    """
    Generate personalized medicine suggestions for a customer based on:
    1. Items they previously purchased
    2. Market basket analysis (items frequently bought together)
    3. Top moving items in inventory
    
    Args:
        customer_id: Customer ID to generate suggestions for
        limit: Number of suggestions to return
        days_back: Look back this many days for purchase history and basket analysis
        exclude_recent_days: Exclude items purchased within this many days
    
    Returns:
        List of suggested items with reasoning
    """
    from .models.core import Item
    from .models.inventory import StockBatch
    
    customer_items = db.session.query(
        SalesBillItem.item_id,
        Item.item_name,
        func.max(SalesBill.bill_date).label('last_purchase_date'),
        func.sum(SalesBillItem.qty_sold).label('total_qty_purchased')
    ).join(SalesBill, SalesBillItem.bill_id == SalesBill.bill_id).join(Item, SalesBillItem.item_id == Item.item_id).filter(
        SalesBill.customer_id == customer_id,
        SalesBill.is_cancelled == False
    ).group_by(SalesBillItem.item_id, Item.item_name).all()
    
    customer_item_ids = {item_id for item_id, _, _, _ in customer_items}
    exclude_cutoff = datetime.now(timezone.utc).date() - timedelta(days=exclude_recent_days)
    recently_bought = {
        item_id for item_id, _, last_date, _ in customer_items
        if last_date and last_date > exclude_cutoff
    }
    
    basket_start = datetime.now(timezone.utc).date() - timedelta(days=days_back)
    related_items = set()
    
    if customer_item_ids:
        related_pairs = db.session.query(
            case(
                (SalesBillItem.item_id.in_(customer_item_ids), None),
                else_=SalesBillItem.item_id
            ).label('related_id'),
            func.count('*').label('co_occurrence')
        ).join(SalesBill, SalesBillItem.bill_id == SalesBill.bill_id).filter(
            SalesBill.bill_date >= basket_start,
            SalesBill.is_cancelled == False
        ).group_by('related_id').order_by(desc('co_occurrence')).limit(limit * 2).all()
        
        for related_id, _ in related_pairs:
            if related_id and related_id not in recently_bought:
                related_items.add(related_id)
    
    top_items_list = get_top_moving_items(limit=limit * 2, days_back=days_back)
    top_item_ids = {item['item_id'] for item in top_items_list if item['item_id'] not in recently_bought}
    
    candidate_ids = list((related_items | top_item_ids) - customer_item_ids - recently_bought)
    
    if not candidate_ids:
        candidate_ids = db.session.query(Item.item_id).filter(
            ~Item.item_id.in_(recently_bought | customer_item_ids)
        ).all()
        candidate_ids = [item_id for (item_id,) in candidate_ids]
    
    # Get full item details for suggestions
    suggestions_data = db.session.query(
        Item.item_id,
        Item.item_name,
        Item.default_selling_price,
        func.coalesce(func.sum(StockBatch.current_qty), 0).label('stock_qty')
    ).outerjoin(StockBatch, Item.item_id == StockBatch.item_id).filter(
        Item.item_id.in_(candidate_ids[:limit * 3])
    ).group_by(Item.item_id, Item.item_name, Item.default_selling_price).all()
    
    suggestions = []
    for item_id, item_name, price, stock in suggestions_data:
        if int(stock) > 0:
            reason = "Popular item"
            if item_id in related_items:
                reason = "Frequently bought with your purchases"
            if item_id in top_item_ids:
                reason = "Top selling medicine"
            
            suggestions.append({
                "item_id": item_id,
                "item_name": item_name,
                "price": float(price or 0),
                "stock": int(stock),
                "reason": reason
            })
    
    return sorted(suggestions, key=lambda x: x['stock'], reverse=True)[:limit]

def get_refill_reminders(days_buffer=5):
    """
    Find customers whose medicine is about to run out.
    """
    today = date_type.today()
    due_cutoff = today + timedelta(days=days_buffer)
    
    reminders = db.session.query(
        CustomerPurchasePattern,
        Customer.customer_name,
        Customer.phone,
        Item.item_name
    ).join(Customer, CustomerPurchasePattern.customer_id == Customer.customer_id)\
     .join(Item, CustomerPurchasePattern.item_id == Item.item_id)\
     .filter(
         CustomerPurchasePattern.is_chronic == True,
         CustomerPurchasePattern.next_expected_date >= today - timedelta(days=2), # Don't show very old ones
         CustomerPurchasePattern.next_expected_date <= due_cutoff
     ).order_by(CustomerPurchasePattern.next_expected_date.asc()).all()
    
    return [
        {
            "id": p.pattern_id,
            "customer_id": p.customer_id,
            "customer_name": name,
            "phone": phone,
            "item_name": item_name,
            "last_purchase": p.last_purchased_date.isoformat(),
            "next_due": p.next_expected_date.isoformat(),
            "days_remaining": (p.next_expected_date - today).days
        }
        for p, name, phone, item_name in reminders
    ]

def get_staff_performance_summary(days_back=30):
    """
    Get high-level performance metrics for all active salesmen.
    """
    from .models.hr import Salesman
    start_date = datetime.now(timezone.utc).date() - timedelta(days=days_back)
    
    staff_stats = db.session.query(
        Salesman.salesman_id,
        Salesman.salesman_name,
        Salesman.salesman_code,
        func.count(SalesBill.bill_id).label('bill_count'),
        func.sum(SalesBill.net_amount).label('total_revenue')
    ).join(SalesBill, Salesman.salesman_id == SalesBill.salesman_id).filter(
        SalesBill.is_cancelled == False,
        SalesBill.bill_date >= start_date
    ).group_by(Salesman.salesman_id, Salesman.salesman_name, Salesman.salesman_code).all()
    
    return [
        {
            "id": sid,
            "name": name,
            "code": code,
            "bills": bills,
            "revenue": round(float(rev), 2),
            "avg_bill": round(float(rev) / bills, 2) if bills > 0 else 0
        }
        for sid, name, code, bills, rev in staff_stats
    ]

def get_staff_detailed_performance(staff_id, days_back=30):
    """
    Generate detailed performance metrics for a specific staff member.
    """
    from .models.hr import Salesman
    from .models.core import ProductCategory
    
    staff = db.session.get(Salesman, staff_id)
    if not staff:
        return None
        
    start_date = datetime.now(timezone.utc).date() - timedelta(days=days_back)
    
    # 1. Sales Trend (Last 30 Days)
    trend_query = db.session.query(
        SalesBill.bill_date,
        func.sum(SalesBill.net_amount).label('daily_rev')
    ).filter(
        SalesBill.salesman_id == staff_id,
        SalesBill.is_cancelled == False,
        SalesBill.bill_date >= start_date
    ).group_by(SalesBill.bill_date).order_by(SalesBill.bill_date).all()
    
    trend = [{"date": d.isoformat(), "revenue": float(r)} for d, r in trend_query]
    
    # 2. Category Distribution
    category_query = db.session.query(
        ProductCategory.category_name,
        func.sum(SalesBillItem.value).label('cat_val')
    ).join(Item, Item.category_id == ProductCategory.category_id)\
     .join(SalesBillItem, SalesBillItem.item_id == Item.item_id)\
     .join(SalesBill, SalesBillItem.bill_id == SalesBill.bill_id)\
     .filter(
        SalesBill.salesman_id == staff_id,
        SalesBill.is_cancelled == False,
        SalesBill.bill_date >= start_date
    ).group_by(ProductCategory.category_name).all()
    
    categories = [{"category": name, "value": float(val)} for name, val in category_query]
    
    # 3. Top Items Sold by this Staff
    top_items = db.session.query(
        Item.item_name,
        func.sum(SalesBillItem.qty_sold).label('qty')
    ).join(SalesBillItem, Item.item_id == SalesBillItem.item_id)\
     .join(SalesBill, SalesBillItem.bill_id == SalesBill.bill_id)\
     .filter(
        SalesBill.salesman_id == staff_id,
        SalesBill.is_cancelled == False,
        SalesBill.bill_date >= start_date
    ).group_by(Item.item_name).order_by(func.sum(SalesBillItem.qty_sold).desc()).limit(5).all()
    
    # 4. Overall Summary
    total_rev = sum(t["revenue"] for t in trend)
    bill_count = db.session.query(func.count(SalesBill.bill_id)).filter(
        SalesBill.salesman_id == staff_id, 
        SalesBill.is_cancelled == False
    ).scalar()
    
    return {
        "staff_info": {"name": staff.salesman_name, "code": staff.salesman_code},
        "summary": {
            "total_revenue": round(total_rev, 2),
            "bill_count": bill_count,
            "avg_bill": round(total_rev / bill_count, 2) if bill_count > 0 else 0
        },
        "trend": trend,
        "categories": categories,
        "top_items": [{"name": n, "qty": int(q)} for n, q in top_items]
    }
