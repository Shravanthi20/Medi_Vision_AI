import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from backend.app_factory import create_app
from backend.extensions import db
from backend.models.core import Item
from backend.models.inventory import StockBatch
from backend.models.sales import SalesBillItem
from backend.models.ai import CustomerPurchasePattern

app = create_app()
with app.app_context():
    keywords = ['sparkler', 'wala', 'fancy', 'razor', 'pop', 'shot', 'firework', 'shampoo']
    
    items = Item.query.all()
    to_delete = []
    for item in items:
        name = (item.item_name or '').lower()
        if any(k in name for k in keywords):
            to_delete.append(item)
            
    print(f"Deleting {len(to_delete)} items...")
    
    for item in to_delete:
        CustomerPurchasePattern.query.filter_by(item_id=item.item_id).delete()
        SalesBillItem.query.filter_by(item_id=item.item_id).delete()
        StockBatch.query.filter_by(item_id=item.item_id).delete()
        db.session.delete(item)
        
    db.session.commit()
    print("Done!")
