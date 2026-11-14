import { useState } from 'react';

function RecipeCard({ recipe }) {
    const [isModalOpen, setIsModalOpen] = useState(false);
    
    // Attempt to parse metadata string if it comes back as string from backend
    // Sometimes powershell returns object, sometimes backend returns map stringified.
    let metadata = {};
    if (typeof recipe.metadata === 'string') {
        try {
            // Very hacky parse if it looks like @{key=value;...}
            const cleanStr = recipe.metadata.replace(/@\{|\}/g, '');
            cleanStr.split(';').forEach(pair => {
                const [k, v] = pair.split('=').map(s => s.trim());
                if (k) metadata[k] = v;
            });
        } catch(e) {}
    } else {
        metadata = recipe.metadata || {};
    }

    let nutrition = {};
    if (typeof recipe.nutrition === 'string') {
        try {
            const cleanStr = recipe.nutrition.replace(/@\{|\}/g, '');
            cleanStr.split(';').forEach(pair => {
                const [k, v] = pair.split('=').map(s => s.trim());
                if (k) nutrition[k] = v;
            });
        } catch(e) {}
    } else {
        nutrition = recipe.nutrition || {};
    }

    return (
      <>
      <div className="glass-panel recipe-card" onClick={() => setIsModalOpen(true)} style={{cursor: 'pointer'}}>
        <div className="recipe-header">
          <h3 className="recipe-title">{recipe.item_name}</h3>
          <span className="recipe-score">{(recipe.score * 100).toFixed(1)}% Match</span>
        </div>
        
        <div className="recipe-meta">
          <div className="meta-item">
             ⏳ {metadata.cookTime || '?'} mins
          </div>
          <div className="meta-item">
             🥩 {metadata.mainProtein || 'Mixed'}
          </div>
          <div className="meta-item">
             🛒 {metadata.ingredientCount || '?'} items
          </div>
          {recipe.missingIngredients && recipe.missingIngredients.length > 0 && (
            <div className="meta-item" style={{color: '#f87171'}}>
               ⚠️ Missing {recipe.missingIngredients.length}
            </div>
          )}
        </div>
  
        <div className="nutrition-grid">
          <div className="nutrition-item">
            <span className="nutri-label">Calories</span>
            <span className="nutri-value">{nutrition.calories ? Math.round(nutrition.calories) : '-'}</span>
          </div>
          <div className="nutrition-item">
            <span className="nutri-label">Protein</span>
            <span className="nutri-value">{nutrition.protein ? Math.round(nutrition.protein) : '-'}g</span>
          </div>
          <div className="nutrition-item">
            <span className="nutri-label">Fat</span>
            <span className="nutri-value">{nutrition.fat ? Math.round(nutrition.fat) : '-'}g</span>
          </div>
        </div>
      </div>

      {isModalOpen && (
        <div className="modal-overlay" onClick={() => setIsModalOpen(false)}>
          <div className="modal-content glass-panel" onClick={e => e.stopPropagation()}>
            <button className="modal-close" onClick={() => setIsModalOpen(false)}>×</button>
            <h2 style={{color: '#60a5fa', marginBottom: '1rem', paddingRight: '2rem'}}>{recipe.item_name}</h2>
            <hr style={{borderColor: 'rgba(255,255,255,0.1)'}} />
            <div className="modal-body">
              {recipe.missingIngredients && recipe.missingIngredients.length > 0 && (
                <div style={{marginBottom: '1.5rem', padding: '1rem', background: 'rgba(239, 68, 68, 0.1)', borderRadius: '8px', border: '1px solid rgba(239, 68, 68, 0.2)'}}>
                  <h4 style={{color: '#f87171', marginBottom: '0.5rem'}}>Missing Ingredients:</h4>
                  <ul style={{paddingLeft: '1.5rem', color: '#fca5a5'}}>
                    {recipe.missingIngredients.map((ing, i) => (
                      <li key={i}>{typeof ing === 'string' ? ing : ing.name}</li>
                    ))}
                  </ul>
                </div>
              )}
              <pre style={{whiteSpace: 'pre-wrap', fontFamily: 'inherit'}}>{recipe.payload}</pre>
            </div>
          </div>
        </div>
      )}
      </>
    );
  }
  
  export default RecipeCard;
