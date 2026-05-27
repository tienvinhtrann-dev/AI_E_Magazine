from app import create_app
app = create_app()
for r in sorted([str(u) for u in app.url_map.iter_rules()]):
    print(r)
