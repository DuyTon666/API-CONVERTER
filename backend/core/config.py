# sys: đụng vào "máy móc nội bộ" của Python lúc đang chạy (ở đây dùng sys.path).
# Path: class xử lý đường dẫn file (thay cho nối chuỗi tay).
import sys
from pathlib import Path

# Hằng số đường dẫn dùng chung cho cả backend — tính từ vị trí file này (__file__),
# lùi lên 3 cấp (.parent.parent.parent: core/ -> backend/ -> gốc project) rồi nối
# thêm tên thư mục đích. Các router/service import lại các biến này thay vì tự
# tính Path(...) riêng từng nơi.
PIPELINE_DIR = Path(__file__).parent.parent.parent / "2.pipeline"
OUTPUT_DIR = Path(__file__).parent.parent.parent / "5.openapi"
DIST_DIR = Path(__file__).parent.parent.parent / "dist"
CONFIG_DIR = Path(__file__).parent.parent.parent / "4.config"
SOURCE_DIR = Path(__file__).parent.parent.parent / "1.docs" / "source" / "api_contract"

# sys.path là list các thư mục Python sẽ tìm khi gặp "import X" — chèn 2.pipeline/
# vào đầu list để dòng "from generator.emitter import ..." ngay dưới tìm được module
# nằm bên trong 2.pipeline/ (nếu không chèn trước, Python sẽ báo "module not found").
sys.path.insert(0, str(PIPELINE_DIR))

# Lấy hàm init_config từ 2.pipeline/generator/emitter.py, đổi tên cục bộ thành
# _init_emitter (dấu _ đầu = quy ước "riêng tư").
from generator.emitter import init_config as _init_emitter

# Gọi ngay — side effect thật của file này: setup cấu hình cho bộ sinh OpenAPI YAML
# (emitter) dùng 4.config/ làm nguồn quy tắc (server-managed fields, response refs...).
_init_emitter(str(CONFIG_DIR))
