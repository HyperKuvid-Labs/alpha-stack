from flask import jsonify
from ..services.addition_service import add_numbers as service_add_numbers
from ..utils.validators import is_valid_number

def add_numbers(request):
    data = request.get_json()
    if not data:
        return jsonify({'error': 'No JSON data provided'}), 400
    num1 = data.get('num1')
    num2 = data.get('num2')
    if num1 is None or num2 is None:
        return jsonify({'error': 'Missing num1 or num2 in request'}), 400
    if not (is_valid_number(num1) and is_valid_number(num2)):
        return jsonify({'error': 'num1 and num2 must be valid numbers'}), 400
    try:
        num1 = float(num1)
        num2 = float(num2)
    except (ValueError, TypeError):
        return jsonify({'error': 'num1 and num2 must be convertible to float'}), 400
    result = service_add_numbers(num1, num2)
    return jsonify({'sum': result, 'status': 'success'}), 200
