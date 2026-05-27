from app import create_app
app = create_app()
with app.test_client() as c:
    r = c.post('/api/auth/google', json={'id_token':'x'})
    print('status', r.status_code)
    print('data', r.get_data(as_text=True))
