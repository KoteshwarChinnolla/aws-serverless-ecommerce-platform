import razorpay
import os

API_KEY = os.getenv("RAZORPAY_API_KEY")
API_SECRET = os.getenv("RAZORPAY_API_SECRET")

client = razorpay.Client(auth=(API_KEY, API_SECRET))

def create_rzp_order(amount_in_rupees, receipt_id):
    try:
        amount_in_paise = int(round(float(amount_in_rupees) * 100))
        order_data = {
            "amount": amount_in_paise,
            "currency": "INR",
            "receipt": receipt_id,
            "payment_capture": 1
        }
        order = client.order.create(data=order_data)
        return {'statusCode': 201, 'body': order}
    except Exception as e:
        return {'statusCode': 500, 'body': {"error": str(e)}}

def verify_rzp_signature(order_id, payment_id, signature):
    try:
        client.utility.verify_payment_signature({
            'razorpay_order_id': order_id,
            'razorpay_payment_id': payment_id,
            'razorpay_signature': signature
        })
        return True
    except razorpay.errors.SignatureVerificationError:
        return False
    except Exception:
        return False
def fetch_rzp(query_params):

    if not query_params:
        return {'statusCode': 400, 'body': {"error": "Query parameters are required"}}

    payment_id = query_params.get("payment_id")
    order_id = query_params.get("order_id")
    refund_id = query_params.get("refund_id")

    if not any([payment_id, order_id, refund_id]):
        return {'statusCode': 400, 'body': {"error": "At least one of payment_id, order_id, or refund_id must be provided"}}

    response_body = {}

    try:
        if order_id:
            response_body["order"] = client.order.fetch(order_id)
            
        if payment_id:
            response_body["payment"] = client.payment.fetch(payment_id)
            
        if refund_id:
            response_body["refund"] = client.refund.fetch(refund_id)
            
        return {'statusCode': 200, 'body': response_body}
        
    except razorpay.errors.BadRequestError as e:
         return {'statusCode': 400, 'body': {"error": "Razorpay Bad Request. Ensure IDs are valid.", "details": str(e)}}
    except Exception as e:
        return {'statusCode': 500, 'body': {"error": str(e)}}

def create_rzp_refund(payment_id, amount_in_rupees, reason="Cancellation"):

    try:
        amount_in_paise = int(round(float(amount_in_rupees) * 100))
        refund_data = {
            "amount": amount_in_paise,
            "notes": {"reason": reason}
        }
        refund = client.refund.create(payment_id, refund_data)
        return {'statusCode': 201, 'body': refund}
    except Exception as e:
        return {'statusCode': 500, 'body': {"error": str(e)}}