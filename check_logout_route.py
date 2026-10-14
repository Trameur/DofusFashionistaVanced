from django.test import Client

client = Client()
response = client.post('/logout/', {'next': '/'})
print(response.status_code)
print(response.headers.get('Location'))
