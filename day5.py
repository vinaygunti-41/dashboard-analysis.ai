from flask import Flask, render_template, request, jsonify, redirect, url_for, session
from flask_cors import CORS
from flask_sqlalchemy import SQLAlchemy
from functools import wraps
import os
import pandas as pd
import hashlib
from datetime import datetime, timezone
import numpy as np
from sklearn.linear_model import LinearRegression

app = Flask(__name__)
app.secret_key = 'your-secret-key-here'

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
UPLOAD_FOLDER = os.path.join(BASE_DIR, 'uploads')
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

DB_PATH = os.path.join(BASE_DIR, 'retail.db')

app.config['SQLALCHEMY_DATABASE_URI'] = f'sqlite:///{DB_PATH}'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# Initialize extensions
db = SQLAlchemy(app)
CORS(app)

def load_dataset_file(file_path):
    if not os.path.isabs(file_path):
        file_path = os.path.join(BASE_DIR, file_path)
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"Dataset file not found: {file_path}")
    if file_path.lower().endswith('.csv'):
        return pd.read_csv(file_path)
    if file_path.lower().endswith(('.xlsx', '.xls')):
        return pd.read_excel(file_path)
    raise ValueError('Unsupported file format')


def find_column(df, candidates):
    for col in candidates:
        if col in df.columns:
            return col
    return None


# ==================== PASSWORD HASHING ====================

def hash_password(password):
    """Simple password hashing for MVP"""
    return hashlib.sha256(password.encode()).hexdigest()

# ==================== MODELS ====================

class User(db.Model):
    __tablename__ = 'users'
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(50), unique=True, nullable=False)
    email = db.Column(db.String(100), unique=True, nullable=False)
    password = db.Column(db.String(100), nullable=False)  # Stores hashed password
    full_name = db.Column(db.String(100))
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

class Dataset(db.Model):
    __tablename__ = 'datasets'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, nullable=False)
    filename = db.Column(db.String(255))
    original_filename = db.Column(db.String(255))
    file_path = db.Column(db.String(500))
    total_rows = db.Column(db.Integer)
    total_columns = db.Column(db.Integer)
    upload_date = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

class Report(db.Model):
    __tablename__ = 'reports'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, nullable=False)
    dataset_id = db.Column(db.Integer)
    report_name = db.Column(db.String(255))
    report_data = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

# ==================== AUTH DECORATOR ====================

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

# ==================== ROUTES ====================

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        
        # Hash the provided password for comparison
        hashed_password = hash_password(password)
        
        user = User.query.filter_by(username=username).first()
        if user and user.password == hashed_password:
        # if username == 'admin' and password == 'admin123':
            session['user_id'] = user.id
            session['username'] = user.username
            return jsonify({'success': True, 'message': 'Login successful'})
        return jsonify({'success': False, 'error': 'Invalid credentials'})
    
    return render_template('login.html')


@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form.get('username')
        email = request.form.get('email')
        password = request.form.get('password')
        full_name = request.form.get('full_name', '')
        
        # Check if user exists
        if User.query.filter_by(username=username).first():
            return jsonify({'success': False, 'error': 'Username already exists'})
        
        if User.query.filter_by(email=email).first():
            return jsonify({'success': False, 'error': 'Email already exists'})
        
        # Hash password before storing
        hashed_password = hash_password(password)
        
        # Create user
        user = User(username=username, email=email, password=hashed_password, full_name=full_name)
        db.session.add(user)
        db.session.commit()
        
        return jsonify({'success': True, 'message': 'Registration successful'})
    
    return render_template('register.html')

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

@app.route('/dashboard')
@login_required
def dashboard():
    return render_template('dashboard.html')

@app.route('/upload')
@login_required
def upload_page():
    return render_template('upload.html')

@app.route('/forecast')
@login_required
def forecast_page():
    return render_template('forecast.html')

@app.route('/api/upload', methods=['POST'])
@login_required
def upload_file():
    try:
        if 'file' not in request.files:
            return jsonify({'error': 'No file uploaded'}), 400
        
        file = request.files['file']
        if file.filename == '':
            return jsonify({'error': 'No file selected'}), 400
        
        # Save file
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = f"{timestamp}_{file.filename}"
        file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        file.save(file_path)
        
        # Read data
        df = load_dataset_file(file_path)
        
        # Save to database
        dataset = Dataset(
            user_id=session['user_id'],
            filename=filename,
            original_filename=file.filename,
            file_path=file_path,
            total_rows=len(df),
            total_columns=len(df.columns)
        )
        db.session.add(dataset)
        db.session.commit()
        
        return jsonify({
            'success': True,
            'message': 'Upload successful',
            'dataset_id': dataset.id,
            'rows': len(df),
            'columns': len(df.columns),
            'preview': df.head(5).to_dict('records')
        })
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/datasets')
@login_required
def get_datasets():
    datasets = Dataset.query.filter_by(user_id=session['user_id']).all()
    return jsonify([{
        'id': d.id,
        'name': d.original_filename,
        'rows': d.total_rows,
        'columns': d.total_columns,
        'date': d.upload_date.strftime('%Y-%m-%d %H:%M')
    } for d in datasets])

@app.route('/api/dashboard-data')
@login_required
def get_dashboard_data():
    try:
        dataset = Dataset.query.filter_by(user_id=session['user_id']).order_by(Dataset.id.desc()).first()
        
        if not dataset:
            return jsonify({
                'total_sales': 0,
                'total_orders': 0,
                'total_customers': 0,
                'total_profit': 0
            })
        
        df = load_dataset_file(dataset.file_path)
        
        kpis = {
            'total_sales': float(df['Sales_Amount'].sum()) if 'Sales_Amount' in df.columns else float(df['Sales'].sum()) if 'Sales' in df.columns else 0,
            'total_orders': len(df),
            'total_customers': int(df['Customer_ID'].nunique()) if 'Customer_ID' in df.columns else 0,
            'total_profit': float(df['Profit'].sum()) if 'Profit' in df.columns else 0
        }
        
        return jsonify(kpis)
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/sales-trend')
@login_required
def get_sales_trend():
    try:
        dataset = Dataset.query.filter_by(user_id=session['user_id']).order_by(Dataset.id.desc()).first()
        
        if not dataset:
            return jsonify({'labels': [], 'values': []})
        
        df = load_dataset_file(dataset.file_path)
        
        date_col = find_column(df, ['Order_Date', 'Date', 'order_date'])
        sales_col = find_column(df, ['Sales_Amount', 'Sales', 'Amount'])
        
        if date_col and sales_col:
            df[date_col] = pd.to_datetime(df[date_col])
            monthly = df.groupby(pd.Grouper(key=date_col, freq='M'))[sales_col].sum()
            
            if len(monthly) > 6:
                monthly = monthly.tail(6)
            
            return jsonify({
                'labels': monthly.index.strftime('%b %Y').tolist(),
                'values': monthly.values.tolist()
            })
        
        return jsonify({'labels': [], 'values': []})
        
    except Exception as e:
        return jsonify({'labels': [], 'values': []})

@app.route('/api/categories')
@login_required
def get_categories():
    try:
        dataset = Dataset.query.filter_by(user_id=session['user_id']).order_by(Dataset.id.desc()).first()
        
        if not dataset:
            return jsonify({'labels': [], 'values': []})
        
        df = load_dataset_file(dataset.file_path)
        
        if 'Category' in df.columns and 'Sales_Amount' in df.columns:
            cat_data = df.groupby('Category')['Sales_Amount'].sum().sort_values(ascending=False).head(6)
            return jsonify({
                'labels': cat_data.index.tolist(),
                'values': cat_data.values.tolist()
            })
        
        return jsonify({'labels': [], 'values': []})
        
    except Exception as e:
        return jsonify({'labels': [], 'values': []})

# ==================== FORECAST ROUTES ====================

@app.route('/api/forecast/datasets')
@login_required
def get_forecast_datasets():
    datasets = Dataset.query.filter_by(user_id=session['user_id']).all()
    return jsonify([{
        'id': d.id,
        'name': d.original_filename,
        'rows': d.total_rows
    } for d in datasets])

@app.route('/api/forecast', methods=['POST'])
@login_required
def generate_forecast():
    try:
        data = request.json
        dataset_id = data.get('dataset_id')
        
        if not dataset_id:
            return jsonify({'error': 'Dataset ID required'}), 400
        
        dataset = Dataset.query.filter_by(id=dataset_id, user_id=session['user_id']).first()
        
        if not dataset:
            return jsonify({'error': 'Dataset not found'}), 404
        
        # Read data
        df = load_dataset_file(dataset.file_path)
        
        # Find date and sales columns
        date_col = find_column(df, ['Order_Date', 'Date', 'order_date', 'Transaction_Date'])
        sales_col = find_column(df, ['Sales_Amount', 'Sales', 'Amount', 'Revenue'])
        
        if not date_col or not sales_col:
            return jsonify({'error': 'Required columns not found (Date and Sales)'}), 400
        
        # Prepare data
        df[date_col] = pd.to_datetime(df[date_col])
        daily_sales = df.groupby(date_col)[sales_col].sum().reset_index()
        daily_sales = daily_sales.sort_values(date_col)
        
        # Get the last 60 days of data for better trend analysis
        if len(daily_sales) > 60:
            recent_data = daily_sales.tail(60)
        else:
            recent_data = daily_sales
        
        # Get values
        recent_values = recent_data[sales_col].values
        
        # Calculate statistics
        avg_daily = np.mean(recent_values)
        std_daily = np.std(recent_values)
        
        # Calculate trend using linear regression
        if len(recent_values) > 3:
            x = np.arange(len(recent_values)).reshape(-1, 1)
            y = recent_values.reshape(-1, 1)
            trend_model = LinearRegression()
            trend_model.fit(x, y)
            trend = float(trend_model.coef_[0][0])  # Daily change
        else:
            trend = 0.0
        
        # Calculate growth rate
        if len(recent_values) > 1:
            first_val = recent_values[0]
            last_val = recent_values[-1]
            if first_val > 0:
                growth_rate = ((last_val - first_val) / first_val) * 100
            else:
                growth_rate = 0
        else:
            growth_rate = 0
        
        # Generate forecast for next 30 days
        forecast_days = 30
        forecast_values = []
        
        for i in range(1, forecast_days + 1):
            # Predict value: trend + some randomness
            predicted = avg_daily + (trend * i)
            
            # Add some seasonality (weekly pattern)
            day_of_week = (i % 7)
            if day_of_week in [5, 6]:  # Weekend (Saturday/Sunday)
                predicted *= 1.25  # 25% higher on weekends
            elif day_of_week == 6:  # Sunday
                predicted *= 0.9  # 10% lower on Sunday
            
            # Ensure prediction is reasonable (not negative, not too extreme)
            predicted = max(predicted, avg_daily * 0.3)  # At least 30% of average
            predicted = min(predicted, avg_daily * 2.5)  # At most 250% of average
            
            forecast_values.append(predicted)
        
        # Generate future dates
        last_date = recent_data[date_col].max()
        future_dates = [last_date + pd.Timedelta(days=i) for i in range(1, forecast_days + 1)]
        
        # ============= CALCULATE ACCURACY =============
        accuracy = 0.5  # Default
        
        if len(recent_values) > 7:
            # Use 80/20 split for validation
            split = int(len(recent_values) * 0.8)
            
            if split > 0 and split < len(recent_values):
                train = recent_values[:split]
                test = recent_values[split:]
                
                if len(test) > 1:
                    # Calculate accuracy using MAPE
                    train_mean = np.mean(train)
                    
                    if train_mean > 0:
                        # Simple forecast: use training mean
                        forecast_test = np.full(len(test), train_mean)
                        
                        # Calculate MAPE (Mean Absolute Percentage Error)
                        mape_values = []
                        for actual, predicted in zip(test, forecast_test):
                            if actual > 0:
                                mape_values.append(abs((actual - predicted) / actual) * 100)
                        
                        if mape_values:
                            mape = np.mean(mape_values)
                            # Convert to accuracy score (100% - MAPE, clamped between 0 and 95)
                            accuracy = max(0, min(95, 100 - mape)) / 100
                        else:
                            accuracy = 0.5
                    else:
                        accuracy = 0.5
                else:
                    accuracy = 0.6
            else:
                accuracy = 0.6
        else:
            # Not enough data, use a reasonable default
            accuracy = 0.5
        
        # Calculate additional metrics
        mae = np.mean(np.abs(recent_values - avg_daily))
        
        # Calculate R² (using mean as baseline)
        if len(recent_values) > 2:
            mean_pred = np.full(len(recent_values), avg_daily)
            ss_tot = np.sum((recent_values - avg_daily) ** 2)
            ss_res = np.sum((recent_values - mean_pred) ** 2)
            if ss_tot > 0:
                r2 = max(0, 1 - (ss_res / ss_tot))
            else:
                r2 = accuracy
        else:
            r2 = accuracy
        
        # Calculate growth for the forecast period
        if forecast_values[0] > 0:
            forecast_growth = ((forecast_values[-1] - forecast_values[0]) / forecast_values[0]) * 100
        else:
            forecast_growth = 0
        
        # Prepare results
        result = {
            'success': True,
            'next_month_total': float(sum(forecast_values)),
            'next_month_avg': float(np.mean(forecast_values)),
            'next_month_max': float(max(forecast_values)),
            'next_month_min': float(min(forecast_values)),
            'forecast_data': {
                'dates': [d.strftime('%Y-%m-%d') for d in future_dates],
                'values': [float(v) for v in forecast_values]
            },
            'historical_data': {
                'dates': recent_data[date_col].dt.strftime('%Y-%m-%d').tolist(),
                'values': recent_data[sales_col].tolist()
            },
            'metrics': {
                'mae': float(mae),
                'r2_score': float(r2),
                'accuracy': float(accuracy),
                'avg_daily': float(avg_daily),
                'std_daily': float(std_daily),
                'trend': float(trend),
                'data_points': len(recent_values)
            },
            'growth_rate': float(forecast_growth),
            'summary': {
                'avg_daily': float(avg_daily),
                'trend': float(trend),
                'growth_rate': float(forecast_growth),
                'total_days': len(recent_values)
            }
        }
        
        return jsonify(result)
        
    except Exception as e:
        import traceback
        print(f"❌ Forecast error: {str(e)}")
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500# ==================== RUN APP ====================

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(debug=True, host='0.0.0.0', port=5000)