import json
from backend.config.settings import INTENTS_PATH, BOOK_INTENTS_PATH

try:
    from pyDatalog import pyDatalog

    PYDATALOG_AVAILABLE = True
    pyDatalog.create_terms("Intent, Response, get_response")

    # Định nghĩa các luật tĩnh cho intent
    # pylint: disable=unsupported-binary-operation
    +get_response("greeting", "Chào bạn! Rất vui được trò chuyện.")  # type: ignore # noqa
    +get_response("goodbye", "Tạm biệt! Hẹn gặp lại nhé.")  # type: ignore # noqa
    +get_response("open_hour", "Chúng tôi mở cửa từ 9h sáng đến 9h tối.")  # type: ignore # noqa
    +get_response(  # type: ignore
        "book_price", "Vui lòng cung cấp tên sách để mình kiểm tra giá nhé!"
    )  # noqa
    +get_response(  # type: ignore
        "find_book", "Bạn muốn tìm sách gì? Cung cấp tên hoặc thể loại nhé!"
    )  # noqa
    +get_response(  # type: ignore
        "order_book", "Bạn muốn đặt sách nào? Mình sẽ hướng dẫn cách đặt nhé!"
    )  # noqa
    +get_response("support", "Mình sẽ chuyển yêu cầu của bạn đến admin ngay!")  # type: ignore # noqa
    +get_response(  # type: ignore
        "promotion",
        "Hiện tại shop có chương trình giảm giá 20% cho sách văn học. Bạn muốn xem chi tiết không?",
    )  # noqa
    +get_response(  # type: ignore
        "order_status", "Vui lòng cung cấp mã đơn hàng để mình kiểm tra trạng thái nhé!"
    )  # noqa
    +get_response("accept", "Cảm ơn bạn đã đồng ý!")  # type: ignore # noqa
    +get_response("unknown", "Xin lỗi, mình chưa hiểu. Bạn muốn hỏi gì?")  # type: ignore # noqa
    +get_response("fallback", "Xin lỗi, mình chưa hiểu. Bạn muốn hỏi gì?")  # type: ignore # noqa
except ImportError:
    PYDATALOG_AVAILABLE = False
    print("⚠️ pyDatalog không khả dụng. Sử dụng logic Python thay thế.")


def load_intents():
    intents = []
    for path in [INTENTS_PATH, BOOK_INTENTS_PATH]:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
            intents.extend(data["intents"])
    return {"intents": intents}


def get_response_from_rules(intent, confidence):
    intents = load_intents()

    if PYDATALOG_AVAILABLE:
        # Truy vấn luật tĩnh
        query_result = get_response(Intent, Response) & (Intent == intent)
        responses = [r for _, r in query_result]
        if responses:
            return responses[0]

    # Fallback logic
    if confidence < 0.5:
        return "Mình không chắc lắm. Bạn có thể nói rõ hơn không?"

    rules = {
        "greeting": "Chào bạn! Rất vui được trò chuyện.",
        "goodbye": "Tạm biệt! Hẹn gặp lại nhé.",
        "open_hour": "Chúng tôi mở cửa từ 9h sáng đến 9h tối.",
        "book_price": "Vui lòng cung cấp tên sách để mình kiểm tra giá nhé!",
        "find_book": "Bạn muốn tìm sách gì? Cung cấp tên hoặc thể loại nhé!",
        "order_book": "Bạn muốn đặt sách nào? Mình sẽ hướng dẫn cách đặt nhé!",
        "support": "Mình sẽ chuyển yêu cầu của bạn đến admin ngay!",
        "promotion": "Hiện tại shop có chương trình giảm giá 20% cho sách văn học. Bạn muốn xem chi tiết không?",
        "order_status": "Vui lòng cung cấp mã đơn hàng để mình kiểm tra trạng thái nhé!",
        "accept": "Cảm ơn bạn đã đồng ý!",
        "unknown": "Xin lỗi, mình chưa hiểu. Bạn muốn hỏi gì?",
        "fallback": "Xin lỗi, mình chưa hiểu. Bạn muốn hỏi gì?",
    }

    if intent in rules:
        return rules[intent]

    for intent_data in intents["intents"]:
        if intent_data["tag"] == intent:
            return (
                intent_data["responses"][0]
                if intent_data["responses"]
                else "Xin lỗi, mình chưa hiểu."
            )

    return "Xin lỗi, mình chưa hiểu. Bạn muốn hỏi gì?"
