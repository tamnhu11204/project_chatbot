import requests

BOOKISH_API_URL = "http://localhost:3001/api"

def search_books(name=None, category=None):
    try:
        query = {}
        if name:
            query["filter"] = f'["name", "{name}"]'
        if category:
            query["filter"] = f'["category", "{category}"]'
        query["limit"] = 5
        response = requests.get(f"{BOOKISH_API_URL}/product/get-all", params=query)
        response.raise_for_status()
        data = response.json()
        print(f"Debug: API response = {data}")
        return data.get("data", [])
    except requests.RequestException as e:
        print(f"Lỗi tìm sách: {e}")
        return []

def get_book_by_id(book_id):
    try:
        response = requests.get(f"{BOOKISH_API_URL}/product/{book_id}")
        response.raise_for_status()
        return response.json().get("data")
    except requests.RequestException as e:
        print(f"Lỗi lấy sách: {e}")
        return None

def get_orders_by_user(user_id):
    try:
        response = requests.get(f"{BOOKISH_API_URL}/order/user/{user_id}")
        response.raise_for_status()
        return response.json().get("data", [])
    except requests.RequestException as e:
        print(f"Lỗi lấy đơn hàng: {e}")
        return []

def get_order_by_id(order_id):
    try:
        response = requests.get(f"{BOOKISH_API_URL}/order/{order_id}")
        response.raise_for_status()
        return response.json().get("data")
    except requests.RequestException as e:
        print(f"Lỗi lấy đơn hàng: {e}")
        return None