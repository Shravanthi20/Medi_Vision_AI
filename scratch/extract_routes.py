from backend.app_factory import create_app
app = create_app()
with app.app_context():
    for rule in app.url_map.iter_rules():
        methods = ','.join(sorted(list(rule.methods - {'HEAD', 'OPTIONS'})))
        print(f"{rule.endpoint} | {methods} | {rule.rule}")
