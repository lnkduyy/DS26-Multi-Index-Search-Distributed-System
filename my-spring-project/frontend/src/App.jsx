import { useState, useEffect } from 'react'
import RecipeCard from './components/RecipeCard'
import AdminView from './components/AdminView'

function App() {
  const [query, setQuery] = useState('')
  const [isSearching, setIsSearching] = useState(false)
  const [taskId, setTaskId] = useState(null)
  const [currentView, setCurrentView] = useState(window.location.pathname === '/admin' ? 'admin' : 'search') // 'search' or 'admin' based on URL path
  const [result, setResult] = useState(null)
  const [error, setError] = useState(null)

  // Polling logic
  useEffect(() => {
    let intervalId;
    if (taskId && isSearching) {
      intervalId = setInterval(async () => {
        try {
          const res = await fetch(`/get?id=${taskId}`);
          const data = await res.json();
          
          if (data.state === 'SUCCESS' || data.state === 'done') {
            setResult(data);
            setIsSearching(false);
            setTaskId(null);
          } else if (data.state === 'QUOTA_EXCEEDED' || data.state === 'quota_exceeded') {
            setError("Hệ thống đang bảo trì do hết token. Vui lòng thử lại sau.");
            setIsSearching(false);
            setTaskId(null);
          } else if (data.state === 'ERROR' || data.state === 'error' || data.state === 'FAILED' || data.state === 'failed') {
            setError("Something went wrong during search.");
            setIsSearching(false);
            setTaskId(null);
          }
        } catch (err) {
          console.error(err);
        }
      }, 2000); // poll every 2 seconds
    }
    return () => clearInterval(intervalId);
  }, [taskId, isSearching]);

  const handleSearch = async (e) => {
    e.preventDefault();
    if (!query.trim()) return;

    setIsSearching(true);
    setResult(null);
    setError(null);

    try {
      const res = await fetch('/search', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ user_query: query })
      });
      
      const id = await res.text();
      setTaskId(id);
    } catch (err) {
      setError("Failed to connect to the server.");
      setIsSearching(false);
    }
  }

  const handleBackToSearch = () => {
    window.history.pushState({}, '', '/');
    setCurrentView('search');
  };

  if (currentView === 'admin') {
    return (
      <div className="app-container">
        <header className="header">
          <div className="title-wrapper">
            <img src="/logo-cute-nobg.png" alt="Epicure Logo" className="app-logo" />
            <h1>Epicure</h1>
          </div>
          <p className="subtitle">Admin Dashboard</p>
        </header>
        <AdminView onBack={handleBackToSearch} />
      </div>
    );
  }

  const hasSearched = isSearching || result !== null || error !== null;

  return (
    <div className="app-container">
      <div className={`hero-section ${hasSearched ? 'hero-top' : 'hero-centered'}`}>
        <header className="header" style={{ position: 'relative' }}>
          <div className="title-wrapper">
            <img src="/logo-cute-nobg.png" alt="Epicure Logo" className="app-logo" />
            <h1>Epicure</h1>
          </div>
          <p>Find the perfect recipe using natural language</p>
        </header>

        <form className="search-container" onSubmit={handleSearch}>
          <input 
            type="text" 
            className="search-input" 
            placeholder="e.g. sweet soup with pork..." 
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            disabled={isSearching}
          />
          <button type="submit" className="search-button" disabled={isSearching || !query.trim()}>
            {isSearching ? 'Searching...' : 'Search'}
          </button>
        </form>
      </div>

      {isSearching && (
        <div className="loading-container glass-panel">
          <div className="pulse-ring"></div>
          <h2>Epicure is thinking...</h2>
          <p>Analyzing ingredients, matching flavors, and calculating nutrition.</p>
        </div>
      )}

      {error && (
        <div className="glass-panel" style={{borderColor: 'var(--warning-color)', color: 'var(--warning-color)'}}>
          {error}
        </div>
      )}

      {result && result.answer && !isSearching && (
        <div className="ai-answer-board">
          <h2>🤖 Epicure Suggests</h2>
          <p dangerouslySetInnerHTML={{ __html: result.answer.replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>') }} />
        </div>
      )}

      {result && !isSearching && (
        <div className="results-grid">
          {result.recipes && result.recipes.slice(0, 9).map((recipe, idx) => (
            <RecipeCard key={idx} recipe={recipe} />
          ))}
        </div>
      )}
    </div>
  )
}

export default App
