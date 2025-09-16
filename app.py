from flask import Flask, render_template, request, redirect, url_for, flash, session
import psycopg2
from psycopg2.extras import RealDictCursor
import os
from datetime import datetime, date, timedelta
import uuid
from werkzeug.utils import secure_filename

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY") or os.urandom(24)
app.config['UPLOAD_FOLDER'] = 'static/uploads'
app.permanent_session_lifetime = timedelta(days=7)

# Kết nối Database
DATABASE_CONFIG = {
    'host': 'localhost',
    'database': 'food_order',
    'user': 'postgres',
    'password': '1234'
}

def get_db_connection():
    try:
        conn = psycopg2.connect(**DATABASE_CONFIG)
        return conn
    except Exception as e:
        print(f"Database connection error: {e}")
        return None

def generate_id(prefix):
    return f"{prefix}{uuid.uuid4().hex[:8].upper()}"

# Routes
@app.route('/')
def index():
    return render_template('index.html')

@app.route('/register')
def register():
    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']
        user_type = request.form['user_type']

        if user_type == 'admin':
            if email == 'admin@mail.com' and password == '12345':
                session['user_type'] = 'admin'
                session['user_id'] = 'admin'
                session['user_name'] = 'Admin'
                session.permanent = True
                return redirect(url_for('admin_dashboard'))
            else:
                flash('Sai tài khoản hoặc mật khẩu admin!', 'danger')
                return redirect(url_for('login'))

        conn = get_db_connection()
        if not conn:
            flash('Lỗi kết nối cơ sở dữ liệu', 'danger')
            return redirect(url_for('login'))
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        try:
            if user_type == 'customer':
                cursor.execute("SELECT * FROM KHACHHANG WHERE Email = %s", (email,))
                user = cursor.fetchone()
                if user and user['matkhau'] == password:
                    session['user_type'] = 'customer'
                    session['user_id'] = user['idkhachhang']
                    session['user_name'] = user['hoten']
                    session.permanent = True
                    return redirect(url_for('customer_dashboard'))
                else:
                    flash('Sai tài khoản hoặc mật khẩu!', 'danger')
                    return redirect(url_for('login'))
            elif user_type == 'delivery':
                cursor.execute("SELECT * FROM NGUOIGIAOHANG WHERE Email = %s", (email,))
                user = cursor.fetchone()
                if user and user['matkhau'] == password:
                    session['user_type'] = 'delivery'
                    session['user_id'] = user['idnguoigiaohang']
                    session['user_name'] = user['hoten']
                    session.permanent = True
                    return redirect(url_for('delivery_dashboard'))
                else:
                    flash('Sai tài khoản hoặc mật khẩu!', 'danger')
                    return redirect(url_for('login'))
            elif user_type == 'seller':
                cursor.execute("SELECT * FROM NGUOIBANHANG WHERE Email = %s", (email,))
                user = cursor.fetchone()
                if user and user['matkhau'] == password:
                    session['user_type'] = 'seller'
                    session['user_id'] = user['idnguoibanhang']
                    session['user_name'] = user['hoten']
                    session.permanent = True
                    return redirect(url_for('seller_dashboard'))
                else:
                    flash('Sai tài khoản hoặc mật khẩu!', 'danger')
                    return redirect(url_for('login'))
            else:
                flash('Loại tài khoản không hợp lệ!', 'danger')
                return redirect(url_for('login'))
        except Exception as e:
            flash(f'Lỗi: {str(e)}', 'danger')
            return redirect(url_for('login'))
        finally:
            cursor.close()
            conn.close()
    return render_template('login.html')

@app.route('/customer-dashboard')
def customer_dashboard():
    if 'user_type' not in session or session['user_type'] != 'customer':
        return redirect(url_for('login'))
    return render_template('customer_dashboard.html')

@app.route('/delivery-dashboard')
def delivery_dashboard():
    if 'user_type' not in session or session['user_type'] != 'delivery':
        return redirect(url_for('login'))
    return render_template('delivery_dashboard.html')

@app.route('/seller-dashboard')
def seller_dashboard():
    if 'user_type' not in session or session['user_type'] != 'seller':
        return redirect(url_for('login'))
    return render_template('seller_dashboard.html')

@app.route('/admin-dashboard')
def admin_dashboard():
    if 'user_type' not in session or session['user_type'] != 'admin':
        return redirect(url_for('login'))
    return render_template('admin_dashboard.html')

#Thanh toán phí thường niên cho seller
@app.route('/seller-payments')
def seller_payments():
    if 'user_type' not in session or session['user_type'] != 'seller':
        return redirect(url_for('login'))
    seller_id = session.get('user_id')
    conn = get_db_connection()
    if not conn:
        flash('Lỗi kết nối cơ sở dữ liệu', 'error')
        return redirect(url_for('seller_dashboard'))
    try:
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        cursor.execute("SELECT * FROM DOTTHANHTOAN WHERE NgayKetThuc >= CURRENT_DATE ORDER BY NgayBatDau DESC")
        current_periods = cursor.fetchall()
        cursor.execute("""
            SELECT t.*, d.TenDotThanhToan, d.NgayBatDau, d.NgayKetThuc
            FROM THANHTOANPHIDUYETRI t
            JOIN DOTTHANHTOAN d ON t.IdDonThanhToan = d.IdDotThanhToan
            WHERE t.IdNguoibanhang = %s
            ORDER BY t.NgayThanhtoan DESC
        """, (seller_id,))
        payment_history = cursor.fetchall()
        cursor.close()
        conn.close()
        return render_template('seller_payments.html', current_periods=current_periods, payment_history=payment_history)
    except Exception as e:
        flash(f'Lỗi: {str(e)}', 'error')
        return redirect(url_for('seller_dashboard'))

@app.route('/seller-make-payment/<period_id>', methods=['GET', 'POST'])
def seller_make_payment(period_id):
    if 'user_type' not in session or session['user_type'] != 'seller':
        return redirect(url_for('login'))
    seller_id = session.get('user_id')
    if request.method == 'POST':
        file = request.files.get('minh_chung')
        if file and file.filename != '':
            filename = secure_filename(file.filename)
            ext = filename.rsplit('.', 1)[-1]
            unique_filename = f"{uuid.uuid4().hex}.{ext}"
            save_path = os.path.join(app.root_path, 'static', 'images', 'payments', unique_filename)
            file.save(save_path)
        else:
            flash('Vui lòng chọn file ảnh minh chứng!', 'danger')
            return redirect(request.url)
        conn = get_db_connection()
        if not conn:
            flash('Lỗi kết nối cơ sở dữ liệu', 'error')
            return redirect(url_for('seller_payments'))
        try:
            cursor = conn.cursor(cursor_factory=RealDictCursor)
            # Kiểm tra đã thanh toán chưa
            cursor.execute("""
                SELECT IdThanhtoan, TrangThai FROM THANHTOANPHIDUYETRI 
                WHERE IdDonThanhToan = %s AND IdNguoibanhang = %s
            """, (period_id, seller_id))
            payment = cursor.fetchone()
            if payment:
                if payment['trangthai'] == 'Da_Duyet':
                    flash('Bạn đã thanh toán cho đợt này rồi!', 'success')
                    return redirect(url_for('seller_payments'))
                elif payment['trangthai'] == 'Cho_Duyet':
                    flash('Bạn đã gửi minh chứng, vui lòng chờ duyệt!', 'info')
                    return redirect(url_for('seller_payments'))
            # Thêm thanh toán mới
            payment_id = generate_id('TT')
            cursor.execute("""
                INSERT INTO THANHTOANPHIDUYETRI 
                (IdThanhtoan, IdDonThanhToan, IdNguoibanhang, NgayThanhtoan, HinhanhminChung, TrangThai)
                VALUES (%s, %s, %s, %s, %s, %s)
            """, (payment_id, period_id, seller_id, datetime.now().date(), unique_filename, 'Cho_Duyet'))
            conn.commit()
            cursor.close()
            conn.close()
            flash('Gửi thanh toán thành công! Vui lòng chờ admin duyệt.', 'success')
            return redirect(url_for('seller_payments'))
        except Exception as e:
            flash(f'Lỗi: {str(e)}', 'error')
            return redirect(url_for('seller_payments'))
    # GET: Hiển thị form
    conn = get_db_connection()
    cursor = conn.cursor(cursor_factory=RealDictCursor)
    cursor.execute("SELECT * FROM DOTTHANHTOAN WHERE IdDotThanhToan = %s", (period_id,))
    period = cursor.fetchone()
    cursor.close()
    conn.close()
    return render_template('seller_make_payment.html', period=period)

# Xác nhận thanh toán
@app.route('/payment-periods')
def payment_periods():
    if 'user_type' not in session or session['user_type'] != 'admin':
        return redirect(url_for('login'))
    conn = get_db_connection()
    if not conn:
        flash('Lỗi kết nối cơ sở dữ liệu', 'error')
        return redirect(url_for('admin_dashboard'))
    
    try:
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        cursor.execute("SELECT * FROM DOTTHANHTOAN ORDER BY NgayBatDau DESC")
        periods = cursor.fetchall()
        today = date.today()
        # Trạng thái cho từng đợt
        for period in periods:
            if period['ngaybatdau'] and period['ngayketthuc']:
                if period['ngaybatdau'] <= today <= period['ngayketthuc']:
                    period['trangthai'] = 'Đang diễn ra'
                elif today < period['ngaybatdau']:
                    period['trangthai'] = 'Sắp diễn ra'
                else:
                    period['trangthai'] = 'Đã kết thúc'
            else:
                period['trangthai'] = 'Chưa xác định'
        cursor.close()
        conn.close()
        return render_template('payment_periods.html', periods=periods)
    except Exception as e:
        flash(f'Lỗi: {str(e)}', 'error')
        return redirect(url_for('admin_dashboard'))

@app.route('/create-payment-period', methods=['GET', 'POST'])
def create_payment_period():
    if 'user_type' not in session or session['user_type'] != 'admin':
        return redirect(url_for('login'))
    if request.method == 'POST':
        conn = get_db_connection()
        if not conn:
            flash('Lỗi kết nối cơ sở dữ liệu', 'error')
            return redirect(url_for('payment_periods'))
        try:
            cursor = conn.cursor()
            period_id = generate_id('DOT')
            cursor.execute("""
                INSERT INTO DOTTHANHTOAN (IdDotThanhToan, TenDotThanhToan, NgayBatDau, NgayKetThuc, MoTa)
                VALUES (%s, %s, %s, %s, %s)
            """, (
                period_id,
                request.form['ten_dot'],
                request.form['ngay_bat_dau'],
                request.form['ngay_ket_thuc'],
                request.form['mo_ta']
            ))
            conn.commit()
            cursor.close()
            conn.close()
            flash('Tạo đợt thanh toán thành công!', 'success')
            return redirect(url_for('payment_periods'))
        except Exception as e:
            flash(f'Lỗi: {str(e)}', 'error')
            return redirect(url_for('payment_periods'))
    
    return render_template('create_payment_period.html')

@app.route('/payment-confirmations')
def payment_confirmations():
    if 'user_type' not in session or session['user_type'] != 'admin':
        return redirect(url_for('login'))
    conn = get_db_connection()
    if not conn:
        flash('Lỗi kết nối cơ sở dữ liệu', 'error')
        return redirect(url_for('admin_dashboard'))
    try:
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        cursor.execute("""
            SELECT t.*, d.TenDotThanhToan, n.HoTen as TenNguoiBan
            FROM THANHTOANPHIDUYETRI t
            JOIN DOTTHANHTOAN d ON t.IdDonThanhToan = d.IdDotThanhToan
            JOIN NGUOIBANHANG n ON t.IdNguoibanhang = n.IdNguoibanhang
            ORDER BY t.NgayThanhtoan DESC
        """)
        payments = cursor.fetchall()
        cursor.close()
        conn.close()
        return render_template('payment_confirmations.html', payments=payments)
    except Exception as e:
        flash(f'Lỗi: {str(e)}', 'error')
        return redirect(url_for('admin_dashboard'))

@app.route('/confirm-payment/<payment_id>')
def confirm_payment(payment_id):
    if 'user_type' not in session or session['user_type'] != 'admin':
        return redirect(url_for('login'))
    conn = get_db_connection()
    if not conn:
        flash('Lỗi kết nối cơ sở dữ liệu', 'error')
        return redirect(url_for('payment_confirmations'))
    try:
        cursor = conn.cursor()
        cursor.execute("""
            UPDATE THANHTOANPHIDUYETRI 
            SET TrangThai = 'Da_Duyet'
            WHERE IdThanhtoan = %s
        """, (payment_id,))
        conn.commit()
        cursor.close()
        conn.close()
        flash('Xác nhận thanh toán thành công!', 'success')
    except Exception as e:
        flash(f'Lỗi: {str(e)}', 'error')
    return redirect(url_for('payment_confirmations'))

@app.route('/reject-payment/<payment_id>')
def reject_payment(payment_id):
    if 'user_type' not in session or session['user_type'] != 'admin':
        return redirect(url_for('login'))
    conn = get_db_connection()
    if not conn:
        flash('Lỗi kết nối cơ sở dữ liệu', 'error')
        return redirect(url_for('payment_confirmations'))
    try:
        cursor = conn.cursor()
        cursor.execute("""
            UPDATE THANHTOANPHIDUYETRI 
            SET TrangThai = 'Tu_Choi'
            WHERE IdThanhtoan = %s
        """, (payment_id,))
        conn.commit()
        cursor.close()
        conn.close()
        flash('Từ chối thanh toán thành công!', 'success')
    except Exception as e:
        flash(f'Lỗi: {str(e)}', 'error')
    return redirect(url_for('payment_confirmations'))

# Duyệt hồ sơ người giao hàng
@app.route('/delivery-applications')
def delivery_applications():
    if 'user_type' not in session or session['user_type'] != 'admin':
        return redirect(url_for('login'))
    conn = get_db_connection()
    if not conn:
        flash('Lỗi kết nối cơ sở dữ liệu', 'error')
        return redirect(url_for('admin_dashboard'))
    try:
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        cursor.execute("""
            SELECT * FROM NGUOIGIAOHANG 
            WHERE TrangThai = 'Cho_Duyet'
            ORDER BY IdNguoigiaohang DESC
        """)
        applications = cursor.fetchall()
        cursor.close()
        conn.close()
        return render_template('delivery_applications.html', applications=applications)
    except Exception as e:
        flash(f'Lỗi: {str(e)}', 'error')
        return redirect(url_for('admin_dashboard'))

@app.route('/approve-delivery/<delivery_id>')
def approve_delivery(delivery_id):
    if 'user_type' not in session or session['user_type'] != 'admin':
        return redirect(url_for('login'))
    conn = get_db_connection()
    if not conn:
        flash('Lỗi kết nối cơ sở dữ liệu', 'error')
        return redirect(url_for('delivery_applications'))
    try:
        cursor = conn.cursor()
        cursor.execute("""
            UPDATE NGUOIGIAOHANG 
            SET TrangThai = 'Da_Duyet'
            WHERE IdNguoigiaohang = %s
        """, (delivery_id,))
        conn.commit()
        cursor.close()
        conn.close()
        flash('Duyệt hồ sơ thành công!', 'success')
    except Exception as e:
        flash(f'Lỗi: {str(e)}', 'error')
    return redirect(url_for('delivery_applications'))

@app.route('/reject-delivery/<delivery_id>')
def reject_delivery(delivery_id):
    if 'user_type' not in session or session['user_type'] != 'admin':
        return redirect(url_for('login'))
    conn = get_db_connection()
    if not conn:
        flash('Lỗi kết nối cơ sở dữ liệu', 'error')
        return redirect(url_for('delivery_applications'))
    try:
        cursor = conn.cursor()
        cursor.execute("""
            UPDATE NGUOIGIAOHANG 
            SET TrangThai = 'Tu_Choi'
            WHERE IdNguoigiaohang = %s
        """, (delivery_id,))
        conn.commit()
        cursor.close()
        conn.close()
        flash('Từ chối hồ sơ thành công!', 'success')
    except Exception as e:
        flash(f'Lỗi: {str(e)}', 'error')
    return redirect(url_for('delivery_applications'))

@app.route('/view-delivery-details/<delivery_id>')
def view_delivery_details(delivery_id):
    if 'user_type' not in session or session['user_type'] != 'admin':
        return redirect(url_for('login'))
    conn = get_db_connection()
    if not conn:
        flash('Lỗi kết nối cơ sở dữ liệu', 'error')
        return redirect(url_for('delivery_applications'))
    try:
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        cursor.execute("""
            SELECT * FROM NGUOIGIAOHANG 
            WHERE IdNguoigiaohang = %s
        """, (delivery_id,))
        delivery_person = cursor.fetchone()
        cursor.close()
        conn.close() 
        if not delivery_person:
            flash('Không tìm thấy thông tin người giao hàng', 'error')
            return redirect(url_for('delivery_applications')) 
        return render_template('delivery_details.html', delivery=delivery_person)
    except Exception as e:
        flash(f'Lỗi: {str(e)}', 'error')
        return redirect(url_for('delivery_applications'))

# Các use case khác
@app.route('/food-menu')
def food_menu():
    return render_template('food_menu.html')

@app.route('/delivery-history')
def delivery_history():
    return render_template('delivery_history.html')

@app.route('/seller-menu-management')
def seller_menu_management():
    return render_template('seller_menu_management.html')

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('index'))

# Duyệt hồ sơ người bán hàng
@app.route('/seller-applications')
def seller_applications():
    if 'user_type' not in session or session['user_type'] != 'admin':
        return redirect(url_for('login'))
    conn = get_db_connection()
    if not conn:
        flash('Lỗi kết nối cơ sở dữ liệu', 'error')
        return redirect(url_for('admin_dashboard'))
    try:
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        cursor.execute("""
            SELECT * FROM NGUOIBANHANG 
            WHERE TrangThai = 'Cho_Duyet'
            ORDER BY IdNguoibanhang DESC
        """)
        applications = cursor.fetchall()
        cursor.close()
        conn.close()
        return render_template('seller_applications.html', applications=applications)
    except Exception as e:
        flash(f'Lỗi: {str(e)}', 'error')
        return redirect(url_for('admin_dashboard'))

@app.route('/approve-seller/<seller_id>')
def approve_seller(seller_id):
    if 'user_type' not in session or session['user_type'] != 'admin':
        return redirect(url_for('login'))
    conn = get_db_connection()
    if not conn:
        flash('Lỗi kết nối cơ sở dữ liệu', 'error')
        return redirect(url_for('seller_applications'))
    try:
        cursor = conn.cursor()
        cursor.execute("""
            UPDATE NGUOIBANHANG 
            SET TrangThai = 'Da_Duyet'
            WHERE IdNguoibanhang = %s
        """, (seller_id,))
        conn.commit()
        cursor.close()
        conn.close()
        flash('Duyệt hồ sơ người bán hàng thành công!', 'success')
    except Exception as e:
        flash(f'Lỗi: {str(e)}', 'error')
    return redirect(url_for('seller_applications'))

@app.route('/reject-seller/<seller_id>')
def reject_seller(seller_id):
    if 'user_type' not in session or session['user_type'] != 'admin':
        return redirect(url_for('login'))
    conn = get_db_connection()
    if not conn:
        flash('Lỗi kết nối cơ sở dữ liệu', 'error')
        return redirect(url_for('seller_applications'))
    try:
        cursor = conn.cursor()
        cursor.execute("""
            UPDATE NGUOIBANHANG 
            SET TrangThai = 'Tu_Choi'
            WHERE IdNguoibanhang = %s
        """, (seller_id,))
        conn.commit()
        cursor.close()
        conn.close()
        flash('Từ chối hồ sơ người bán hàng thành công!', 'success')
    except Exception as e:
        flash(f'Lỗi: {str(e)}', 'error')
    return redirect(url_for('seller_applications'))

@app.route('/view-seller-details/<seller_id>')
def view_seller_details(seller_id):
    if 'user_type' not in session or session['user_type'] != 'admin':
        return redirect(url_for('login'))
    conn = get_db_connection()
    if not conn:
        flash('Lỗi kết nối cơ sở dữ liệu', 'error')
        return redirect(url_for('seller_applications'))
    try:
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        cursor.execute("""
            SELECT * FROM NGUOIBANHANG 
            WHERE IdNguoibanhang = %s
        """, (seller_id,))
        seller = cursor.fetchone()
        cursor.close()
        conn.close()
        if not seller:
            flash('Không tìm thấy thông tin người bán hàng', 'error')
            return redirect(url_for('seller_applications'))
        return render_template('seller_details.html', seller=seller)
    except Exception as e:
        flash(f'Lỗi: {str(e)}', 'error')
        return redirect(url_for('seller_applications'))
@app.before_request
def check_session_validity():
    if 'user_type' in session:
        # Kiểm tra session còn hợp lệ không (có thể thêm logic sau này)
        pass

if __name__ == '__main__':
    app.run(debug=True)
