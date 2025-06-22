import re
import json
import requests
import urllib.parse
from datetime import datetime
from backend.config.settings import INTENTS_PATH, BOOK_INTENTS_PATH
from backend.logic.mongo_logger import chat_logs
from transformers import AutoTokenizer

BASE_URL = "http://localhost:3001"
tokenizer = AutoTokenizer.from_pretrained("vinai/phobert-base")

def extract_book_name(message):
    """Improved book name extraction with multiple fallback methods"""
    message = message.strip().lower()
    
    # 1. First try specific Vietnamese search patterns
    search_patterns = [
        r'tìm sách (.+)',
        r'sách (.+)',
        r'cuốn sách (.+)',
        r'cuốn (.+)',
        r'quyển sách (.+)',
        r'quyển (.+)',
        r'cho mình (.+)',
        r'có sách (.+) không',
        r'(.+) có không',
        r'giá sách (.+)',
        r'sách (.+) giá bao nhiêu',
        r'thông tin sách (.+)',
        r'chi tiết sách (.+)'
    ]
    
    for pattern in search_patterns:
        match = re.search(pattern, message)
        if match:
            book_name = match.group(1).strip()
            # Clean up the book name
            book_name = re.sub(r'(bao nhiêu|giá|nội dung|mô tả|chi tiết|đâu rồi|gì|nào)\s*$', '', book_name).strip()
            if book_name:
                print(f"Debug: Pattern matched book_name='{book_name}'")
                return book_name.capitalize()
    
    # 2. Try PhoBERT tokenization for more complex cases
    try:
        inputs = tokenizer(message, return_tensors="pt", truncation=True, padding=True, max_length=64)
        tokens = tokenizer.convert_ids_to_tokens(inputs["input_ids"][0])
        stopwords = {"là", "bao_nhiêu", "có", "không", "gì", "thế_nào", "nào", "đi", "cho", "tìm", "sách"}
        potential_name = []
        current_phrase = []
        
        for token in tokens:
            if token in ["[PAD]", "[CLS]", "[SEP]"]:
                continue
            if token.startswith("##"):
                current_phrase[-1] = current_phrase[-1] + token.replace("##", "")
            else:
                if current_phrase and token not in stopwords:
                    current_phrase.append(token.replace("_", " "))
                elif token not in stopwords:
                    current_phrase = [token.replace("_", " ")]
                else:
                    if current_phrase:
                        potential_name.append(" ".join(current_phrase).strip())
                        current_phrase = []
        
        if current_phrase:
            potential_name.append(" ".join(current_phrase).strip())
        
        book_name = max(potential_name, key=len, default="") if potential_name else ""
        if book_name:
            print(f"Debug: PhoBERT extracted book_name='{book_name}'")
            return book_name.capitalize()
    except Exception as e:
        print(f"PhoBERT tokenization error: {e}")

    # 3. Fallback to simple word extraction
    stopwords = {"là", "bao nhiêu", "có", "không", "gì", "thế nào", "nào", "đi", "cho", "tìm", "sách"}
    words = message.split()
    candidates = []
    current_phrase = []
    
    for word in words:
        if word not in stopwords:
            current_phrase.append(word)
        else:
            if current_phrase:
                candidates.append(" ".join(current_phrase))
                current_phrase = []
    if current_phrase:
        candidates.append(" ".join(current_phrase))
    
    book_name = max(candidates, key=len, default="") if candidates else ""
    print(f"Debug: Fallback extracted book_name='{book_name}'")
    return book_name.capitalize() if book_name else ""

def load_intents():
    """Load intents from JSON files with error handling"""
    intents = []
    for path in [INTENTS_PATH, BOOK_INTENTS_PATH]:
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
                intents.extend(data["intents"])
        except FileNotFoundError:
            print(f"Warning: File not found: {path}")
        except json.JSONDecodeError:
            print(f"Error: Invalid JSON in file: {path}")
    return {"intents": intents}

def match_intent(user_input, intents, context_data):
    """Improved intent matching with better context handling"""
    user_input = user_input.lower().strip()
    book_name = extract_book_name(user_input)
    print(f"Debug: match_intent book_name='{book_name}'")
    
    # Check for direct book-related queries first
    if any(phrase in user_input for phrase in ['tìm sách', 'sách', 'cuốn sách', 'quyển sách']):
        if book_name:
            return "find_book", [], {"book_name": book_name}
    
    if any(phrase in user_input for phrase in ['bao nhiêu tiền', 'giá bao nhiêu', 'bao nhiêu', 'giá sách']):
        if book_name:
            return "book_price", [], {"book_name": book_name}
        elif context_data.get("book_name"):
            return "book_price", [], {"book_name": context_data["book_name"]}
    
    if any(phrase in user_input for phrase in ['nội dung', 'mô tả', 'chi tiết', 'thông tin']):
        if book_name:
            return "book_details", [], {"book_name": book_name}
        elif context_data.get("book_name"):
            return "book_details", [], {"book_name": context_data["book_name"]}
    
    # Check for other intents with pattern matching
    for intent in intents["intents"]:
        for pattern in intent["patterns"]:
            pattern_regex = re.sub(r"\{(\w+)\}", r"(?P<\1>.+?)", pattern)
            match = re.search(pattern_regex, user_input, re.IGNORECASE)
            if match:
                placeholders = re.findall(r"\{(\w+)\}", pattern)
                captured_values = match.groups()
                context = {placeholders[i]: captured_values[i] for i in range(len(placeholders))}
                if book_name and "book_name" not in context:
                    context["book_name"] = book_name
                price_match = re.search(r"(\d+)(?: ngàn|k)?", user_input, re.IGNORECASE)
                if price_match:
                    context["price"] = int(price_match.group(1)) * (1000 if "ngàn" in user_input.lower() or "k" in user_input.lower() else 1)
                print(f"Debug: Matched intent='{intent['tag']}', context={context}")
                return intent["tag"], intent["responses"], context
    
    # Fallback to context if available
    if context_data.get("book_name"):
        if any(keyword in user_input for keyword in ["bao nhiêu", "giá"]):
            return "book_price", [], {"book_name": context_data["book_name"]}
        if any(keyword in user_input for keyword in ["nội dung", "mô tả"]):
            return "book_details", [], {"book_name": context_data["book_name"]}
    
    return "unknown", ["Xin lỗi, mình chưa hiểu. Bạn muốn hỏi gì?"], {"book_name": book_name} if book_name else {}

def get_book_by_id(book_id):
    """Get book details by ID with better error handling"""
    try:
        response = requests.get(
            f"{BASE_URL}/api/product/get-detail/{urllib.parse.quote(book_id)}",
            timeout=5
        )
        response.raise_for_status()
        data = response.json()
        if data.get("status") == "OK":
            return data.get("data")
        print(f"API Error: {data.get('message', 'Unknown error')}")
        return None
    except requests.exceptions.RequestException as e:
        print(f"Request failed: {e}")
        return None

def search_books(name=None, category=None, min_price=None, limit=5):
    """Improved book search with parameters"""
    try:
        params = {}
        if name:
            params["name"] = name.strip()
        if category:
            params["category"] = category.strip()
        if min_price:
            params["price[$gt]"] = min_price
        params["limit"] = limit
        
        response = requests.get(
            f"{BASE_URL}/api/product/get-all",
            params=params,
            timeout=5
        )
        response.raise_for_status()
        print(f"Debug: API call: {response.url}")
        return response.json().get("data", [])
    except requests.exceptions.RequestException as e:
        print(f"Search failed: {e}")
        return []

def get_order_by_id(order_id):
    """Get order details with better error handling"""
    try:
        response = requests.get(
            f"{BASE_URL}/api/order/get-detail/{urllib.parse.quote(order_id)}",
            timeout=5
        )
        response.raise_for_status()
        data = response.json()
        if data.get("status") == "OK":
            return data.get("data")
        print(f"API Error: {data.get('message', 'Unknown error')}")
        return None
    except requests.exceptions.RequestException as e:
        print(f"Request failed: {e}")
        return None

def get_response_from_rules(intent, confidence, user_input, session_id, user_id):
    """Main response handler with improved logic"""
    print(f"\n=== New Request ===")
    print(f"User Input: {user_input}")
    print(f"Detected Intent: {intent}")
    print(f"Confidence: {confidence}")
    
    intents = load_intents()
    
    try:
        context = chat_logs.find_one(
            {"session_id": session_id, "user": {"$ne": user_input}},
            sort=[("timestamp", -1)]
        )
        context_data = context.get("context", {}) if context else {}
    except Exception as e:
        print(f"MongoDB Error: {e}")
        context_data = {}

    def save_context(data):
        try:
            chat_logs.update_one(
                {"session_id": session_id, "user": user_input},
                {
                    "$set": {
                        "context": data,
                        "timestamp": datetime.now(),
                        "last_input": user_input,
                        "user_id": user_id
                    }
                },
                upsert=True
            )
        except Exception as e:
            print(f"MongoDB Save Error: {e}")

    # Extract book name if not in context
    if not context_data.get("book_name"):
        book_name = extract_book_name(user_input)
        if book_name:
            context_data["book_name"] = book_name
            save_context(context_data)

    # If confidence is low, ask for clarification
    if confidence < 0.6:
        save_context({"intent": intent})
        if context_data.get("book_name"):
            return {
                "response": f"Mình không chắc về yêu cầu của bạn. Bạn muốn hỏi về sách '{context_data['book_name']}' phải không?",
                "context": context_data
            }
        return {
            "response": "Mình chưa hiểu rõ ý bạn. Bạn có thể nói rõ hơn không?",
            "context": context_data
        }

    # Get matched intent (may override the detected intent)
    matched_intent, responses, captured_context = match_intent(user_input, intents, context_data)
    if matched_intent != "unknown":
        intent = matched_intent
        context_data.update(captured_context)
        save_context(context_data)

    # Handle specific intents
    if intent == "book_price":
        book_name = context_data.get("book_name")
        if not book_name:
            return {
                "response": "Bạn muốn biết giá sách nào? Hãy cho mình biết tên sách nhé!",
                "context": context_data
            }
        
        books = search_books(name=book_name)
        if books:
            book = books[0]
            price = book.get("price", 0)
            discount = book.get("discount", 0)
            final_price = price * (1 - discount/100) if discount else price
            
            response = f"Sách '{book.get('name', book_name)}' có giá {price:,} VND"
            if discount:
                response += f" (giảm {discount}% còn {final_price:,} VND)"
            response += ". Bạn muốn đặt sách này không?"
            
            context_data.update({
                "book_name": book.get("name"),
                "book_id": str(book["_id"]),
                "price": price,
                "discount": discount
            })
            save_context(context_data)
            
            return {
                "response": response,
                "context": context_data,
                "books": [{"id": book["_id"], "name": book.get("name")}]
            }
        else:
            return {
                "response": f"Không tìm thấy sách '{book_name}'. Bạn có thể kiểm tra lại tên sách không?",
                "context": context_data
            }

    elif intent == "find_book":
        book_name = context_data.get("book_name")
        if not book_name:
            return {
                "response": "Bạn muốn tìm sách gì? Hãy cho mình biết tên sách nhé!",
                "context": context_data
            }
        
        books = search_books(name=book_name, limit=3)
        if books:
            response = f"Mình tìm thấy {len(books)} sách phù hợp:\n"
            for i, book in enumerate(books, 1):
                response += f"{i}. {book.get('name')} - {book.get('price', '?')} VND\n"
            response += "Bạn muốn biết thêm về sách nào?"
            
            context_data.update({
                "recent_books": [{"id": str(book["_id"]), "name": book.get("name")} for book in books]
            })
            save_context(context_data)
            
            return {
                "response": response,
                "context": context_data,
                "books": [{"id": book["_id"], "name": book.get("name")} for book in books]
            }
        else:
            # Suggest popular books if no matches found
            popular_books = search_books(limit=3)
            if popular_books:
                book_list = ", ".join([book.get("name") for book in popular_books])
                return {
                    "response": f"Không tìm thấy sách '{book_name}'. Bạn có thể tham khảo các sách phổ biến: {book_list}",
                    "context": context_data,
                    "books": [{"id": book["_id"], "name": book.get("name")} for book in popular_books]
                }
            return {
                "response": f"Không tìm thấy sách '{book_name}'. Bạn vui lòng kiểm tra lại tên sách!",
                "context": context_data
            }

    elif intent == "book_details":
        book_name = context_data.get("book_name")
        book_id = context_data.get("book_id")
        
        if not (book_name or book_id):
            return {
                "response": "Bạn muốn xem thông tin sách nào? Hãy cho mình biết tên sách nhé!",
                "context": context_data
            }
        
        book = None
        if book_id:
            book = get_book_by_id(book_id)
        elif book_name:
            books = search_books(name=book_name, limit=1)
            if books:
                book = books[0]
                book_id = str(book["_id"])
        
        if book:
            response = (f"Thông tin sách '{book.get('name', book_name)}':\n"
                       f"- Tác giả: {book.get('author', 'Chưa cập nhật')}\n"
                       f"- Giá: {book.get('price', '?')} VND\n"
                       f"- Mô tả: {book.get('description', 'Chưa có mô tả')[:200]}...\n"
                       "Bạn muốn đặt sách này không?")
            
            context_data.update({
                "book_name": book.get("name"),
                "book_id": book_id,
                "author": book.get("author"),
                "price": book.get("price")
            })
            save_context(context_data)
            
            return {
                "response": response,
                "context": context_data,
                "books": [{"id": book["_id"], "name": book.get("name")}]
            }
        else:
            return {
                "response": f"Không tìm thấy thông tin sách '{book_name or book_id}'. Bạn vui lòng kiểm tra lại!",
                "context": context_data
            }

    elif intent == "promotion":
        try:
            response = requests.get(f"{BASE_URL}/api/promotion/get-all", timeout=5)
            response.raise_for_status()
            promotions = response.json().get("data", [])[:3]
            
            if promotions:
                response = "Hiện có các chương trình khuyến mãi:\n"
                for promo in promotions:
                    response += f"- {promo.get('name')}: Giảm {promo.get('discount', 0)}%\n"
                response += "Bạn muốn xem chi tiết chương trình nào?"
                
                save_context({
                    "recent_promotions": [{
                        "id": promo["_id"],
                        "name": promo.get("name"),
                        "discount": promo.get("discount")
                    } for promo in promotions]
                })
                
                return {
                    "response": response,
                    "context": context_data,
                    "promotions": promotions
                }
            else:
                return {
                    "response": "Hiện không có chương trình khuyến mãi nào. Mình sẽ thông báo khi có ưu đãi mới!",
                    "context": context_data
                }
        except requests.RequestException as e:
            print(f"Promotion API Error: {e}")
            return {
                "response": "Hiện không thể kiểm tra khuyến mãi. Bạn vui lòng thử lại sau!",
                "context": context_data
            }

    # Default responses for common intents
    default_responses = {
        "greeting": "Chào bạn! Mình có thể giúp gì cho bạn về sách?",
        "goodbye": "Cảm ơn bạn! Chúc bạn một ngày tốt lành!",
        "open_hour": "Cửa hàng mở cửa từ 8h sáng đến 10h tối tất cả các ngày trong tuần.",
        "support": "Mình đã ghi nhận yêu cầu hỗ trợ. Admin sẽ liên hệ với bạn sớm nhất!",
        "order_book": "Bạn muốn đặt sách nào? Hãy cho mình biết tên sách nhé!",
        "order_status": "Bạn vui lòng cung cấp mã đơn hàng để mình kiểm tra tình trạng giúp bạn!",
        "unknown": "Xin lỗi, mình chưa hiểu ý của bạn. Bạn có thể hỏi về giá sách, thông tin sách hoặc khuyến mãi!"
    }
    
    if intent in default_responses:
        save_context({"intent": intent})
        return {
            "response": default_responses[intent],
            "context": context_data
        }
    
    # Final fallback
    save_context({"intent": intent})
    return {
        "response": "Xin lỗi, mình chưa hiểu. Bạn có thể hỏi về giá sách, thông tin sách hoặc khuyến mãi!",
        "context": context_data
    }