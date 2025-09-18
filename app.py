import os
from flask import Flask, render_template, request, redirect, url_for, session, flash, send_from_directory
import sqlite3
from models import db, Product, Order
from werkzeug.utils import secure_filename
from models import db, Product   # giả sử bạn có model Product
import json
from sqlalchemy.exc import IntegrityError
from slugify import slugify  # optional helper; we'll fallback if not installed

UPLOAD_FOLDER = 'static/uploads'
ALLOWED_EXT = {'png','jpg','jpeg','gif'}

def create_app():
    app = Flask(__name__)
    app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///store.db'
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    app.config['SECRET_KEY'] = 'dev-secret'  # đổi khi production
    app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
    os.makedirs(UPLOAD_FOLDER, exist_ok=True)
    db.init_app(app)
    return app

app = create_app()

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.',1)[1].lower() in ALLOWED_EXT

with app.app_context():
    db.create_all()
    if Product.query.count() == 0:
        p = Product(
            name='Xi măng ABC 50kg',
            slug='xi-mang-abc-50kg',
            description='Xi măng chất lượng',
            price=95000,
            stock=120,
            category='Vật liệu cơ bản'
        )
        db.session.add(p)
        db.session.commit()

@app.route('/')
def index():
    q = request.args.get('q','')
    category = request.args.get('category','')
    products = Product.query
    if q:
        products = products.filter(Product.name.ilike(f'%{q}%'))
    if category:
        products = products.filter_by(category=category)
    products = products.all()
    return render_template('index.html', products=products, q=q)

@app.route('/product/<slug>')
def product_detail(slug):
    product = Product.query.filter_by(slug=slug).first_or_404()
    return render_template('product.html', product=product)

# simple cart in session
def _get_cart():
    return session.setdefault('cart', {})

@app.route('/cart')
def cart_view():
    cart = _get_cart()
    items = []
    total = 0.0
    for pid, qty in cart.items():
        p = Product.query.get(int(pid))
        if not p: continue
        subtotal = p.price * qty
        total += subtotal
        items.append({'product':p, 'qty':qty, 'subtotal':subtotal})
    return render_template('cart.html', items=items, total=total)

@app.route('/cart/add/<int:product_id>', methods=['POST','GET'])
def cart_add(product_id):
    qty = int(request.values.get('qty',1))
    cart = _get_cart()
    cart[str(product_id)] = cart.get(str(product_id),0) + qty
    session['cart'] = cart
    flash('Đã thêm vào giỏ hàng')
    # 👉 Sau khi thêm xong quay lại trang chủ
    return redirect(url_for("index"))

@app.route('/cart/remove/<int:product_id>')
def cart_remove(product_id):
    cart = _get_cart()
    cart.pop(str(product_id), None)
    session['cart'] = cart
    return redirect(url_for('cart_view'))

@app.route('/checkout', methods=['POST','GET'])
def checkout():
    cart = _get_cart()
    if not cart:
        flash('Giỏ hàng trống')
        return redirect(url_for('index'))
    # build order
    items = []
    total = 0.0
    for pid, qty in cart.items():
        p = Product.query.get(int(pid))
        if not p:
            continue
        items.append({'id': p.id, 'name': p.name, 'qty': qty, 'price': p.price})
        total += p.price * qty
        # optionally decrement stock here
    order = Order(total=total, items=json.dumps(items, ensure_ascii=False))
    db.session.add(order)
    db.session.commit()
    session['cart'] = {}
    flash(f'Đặt hàng thành công. Mã đơn: {order.id}')
    return redirect(url_for('index'))

# Admin crud (no auth in this example)
@app.route('/admin')
def admin_index():
    products = Product.query.all()
    return render_template('admin.html', products=products)

@app.route('/admin/add', methods=['GET','POST'])
def admin_add():
    if request.method == "POST":
        name = request.form["name"]
        price = float(request.form["price"])
        stock = int(request.form.get("stock", 0))
        category = request.form.get("category", "")
        description = request.form.get("description", "")

        slug = slugify(name)  # ✅ Tạo slug từ name

        # Xử lý ảnh
        image_file = request.files.get("image")
        image_path = None
        if image_file and image_file.filename != "":
            filename = secure_filename(image_file.filename)
            image_path = os.path.join(app.config["UPLOAD_FOLDER"], filename)
            image_file.save(image_path)

        # Lưu DB
        p = Product(
            name=name,
            slug=slug,  # ✅ Bổ sung slug vào đây
            price=price,
            stock=stock,
            category=category,
            description=description,
            image=image_path
        )
        db.session.add(p)
        try:
            db.session.commit()
        except IntegrityError:
            db.session.rollback()
            flash("Tên sản phẩm đã tồn tại hoặc có lỗi dữ liệu (slug trùng?)", "error")
            return redirect(url_for("admin_add"))

        return redirect(url_for("admin_add"))

    return render_template("admin_add.html")


@app.route('/admin/delete/<int:id>')
def admin_delete(id):
    p = Product.query.get_or_404(id)
    db.session.delete(p)
    db.session.commit()
    flash('Đã xóa')
    return redirect(url_for('admin_index'))


@app.route("/register", methods=["POST"])
def register():
    username = request.form["username"]
    company = request.form["company"]
    president = request.form["president"]

    # Lưu vào database
    conn = sqlite3.connect("data.db")
    c = conn.cursor()
    c.execute("INSERT INTO users (username, company, president) VALUES (?, ?, ?)",
              (username, company, president))
    conn.commit()
    conn.close()

    # Lưu vào session để hiển thị ngay
    session["username"] = username
    session["company"] = company
    session["president"] = president

    return redirect(url_for("congno"))

@app.route("/congno")
def congno():
    return render_template("congno.html")

# static upload serve (dev)
@app.route('/uploads/<path:filename>')
def uploaded_file(filename):
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename)

if __name__ == '__main__':
    app.run(debug=True)
