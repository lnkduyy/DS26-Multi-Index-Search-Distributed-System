import { useState } from 'react';

function AdminView({ onBack }) {
    const [isAuthenticated, setIsAuthenticated] = useState(false);
    const [token, setToken] = useState('');
    const [password, setPassword] = useState('');
    const [loginError, setLoginError] = useState('');

    const [dishData, setDishData] = useState({
        name: '',
        ingredients: '',
        cookingMethod: ''
    });
    
    const [status, setStatus] = useState({ type: '', message: '' });
    const [isLoading, setIsLoading] = useState(false);

    const handleLogin = async (e) => {
        e.preventDefault();
        try {
            const res = await fetch('/api/auth/login', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ password })
            });

            if (res.ok) {
                const data = await res.json();
                setToken(data.token);
                setIsAuthenticated(true);
                setLoginError('');
            } else {
                setLoginError('Invalid credentials');
            }
        } catch (err) {
            setLoginError('Failed to connect to server');
        }
    };

    const handleSubmitDish = async (e) => {
        e.preventDefault();
        setIsLoading(true);
        setStatus({ type: '', message: '' });

        try {
            // Chuẩn hóa dữ liệu theo chuẩn LLM / backend
            const payload = {
                name: dishData.name.trim(),
                ingredients: dishData.ingredients.split(',').map(item => item.trim()).filter(item => item.length > 0),
                cookingMethod: dishData.cookingMethod.trim()
            };

            const response = await fetch('/api/dishes', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'Authorization': `Bearer ${token}`
                },
                body: JSON.stringify(payload)
            });

            if (!response.ok) {
                throw new Error('Failed to submit dish. Server returned ' + response.status);
            }

            setStatus({ type: 'success', message: 'Dish successfully ingested into the cluster!' });
            setDishData({ name: '', ingredients: '', cookingMethod: '' });
        } catch (error) {
            setStatus({ type: 'error', message: error.message });
        } finally {
            setIsLoading(false);
        }
    };

    if (!isAuthenticated) {
        return (
            <div className="admin-login-container glass-panel">
                <button className="back-btn" onClick={onBack}>← Back to Search</button>
                <h2>Admin Login</h2>
                <form onSubmit={handleLogin} className="admin-form">
                    <div className="form-group">
                        <label>Password</label>
                        <input 
                            type="password" 
                            value={password}
                            onChange={(e) => setPassword(e.target.value)}
                            placeholder="Enter admin password..."
                            className="search-input"
                            autoFocus
                        />
                    </div>
                    {loginError && <p className="error-text">{loginError}</p>}
                    <button type="submit" className="search-button">Login</button>
                </form>
            </div>
        );
    }

    return (
        <div className="admin-dashboard glass-panel">
            <button className="back-btn" onClick={onBack}>← Back to Search</button>
            <h2 style={{ marginBottom: '1.5rem', color: '#60a5fa' }}>Ingest New Recipe</h2>
            
            <form onSubmit={handleSubmitDish} className="admin-form">
                <div className="form-group">
                    <label>Recipe Name</label>
                    <input 
                        type="text" 
                        required
                        value={dishData.name}
                        onChange={(e) => setDishData({...dishData, name: e.target.value})}
                        className="search-input"
                        placeholder="e.g. Grandma's Fried Chicken"
                    />
                </div>
                
                <div className="form-group">
                    <label>Ingredients (comma separated)</label>
                    <textarea 
                        required
                        value={dishData.ingredients}
                        onChange={(e) => setDishData({...dishData, ingredients: e.target.value})}
                        className="search-input"
                        placeholder="e.g. 1 whole chicken, 2 cups flour, 1 tsp salt, oil for frying"
                        rows="3"
                        style={{ borderRadius: '1rem', resize: 'vertical' }}
                    />
                </div>

                <div className="form-group">
                    <label>Cooking Method / Instructions</label>
                    <textarea 
                        required
                        value={dishData.cookingMethod}
                        onChange={(e) => setDishData({...dishData, cookingMethod: e.target.value})}
                        className="search-input"
                        placeholder="e.g. Step 1: Heat the oil. Step 2: Coat the chicken..."
                        rows="6"
                        style={{ borderRadius: '1rem', resize: 'vertical' }}
                    />
                </div>

                {status.message && (
                    <div className={`status-message ${status.type}`}>
                        {status.message}
                    </div>
                )}

                <button type="submit" className="search-button" disabled={isLoading} style={{ width: '100%', marginTop: '1rem' }}>
                    {isLoading ? 'Ingesting...' : 'Add Recipe to Cluster'}
                </button>
            </form>
        </div>
    );
}

export default AdminView;
