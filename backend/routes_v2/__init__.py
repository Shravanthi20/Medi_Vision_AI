"""v2 API Blueprint — new endpoints under /api/v2/ prefix."""

from flask import Blueprint

v2_bp = Blueprint('v2', __name__, url_prefix='/api/v2')


@v2_bp.route('/health', methods=['GET'])
def health_check():
    """Quick sanity check that the v2 API is live."""
    from flask import jsonify
    return jsonify({'status': 'ok', 'api_version': '2.0'})
