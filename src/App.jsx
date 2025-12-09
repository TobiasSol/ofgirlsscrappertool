import React, { useState, useEffect, useMemo, useRef } from 'react';
import { 
  Search, RefreshCw, Trash2, Mail, Instagram, 
  CheckCircle, AlertCircle, Plus, Lock, EyeOff, Activity, ArrowUpDown, XCircle, Loader2, Ban, Heart, Copy, Check, GripVertical, Play, ExternalLink, Globe, UserPlus, Menu, LogOut
} from 'lucide-react';

const API_URL = "/api"; 

// --- HELPER ---
const formatDate = (isoString) => {
  if (!isoString) return "-";
  try {
    return new Date(isoString).toLocaleDateString('de-DE', {
      day: '2-digit', month: '2-digit', year: 'numeric'
    });
  } catch (e) { return isoString; }
};

const TabButton = ({ active, label, count, onClick, color = "purple", icon }) => {
    const baseClass = "px-3 py-2 rounded-lg text-sm font-bold transition-all flex items-center gap-2 whitespace-nowrap";
    const activeClass = active 
        ? `bg-${color}-100 text-${color}-700 border border-${color}-200 shadow-sm` 
        : "text-slate-500 hover:bg-slate-50 border border-transparent";
    
    return (
        <button onClick={onClick} className={`${baseClass} ${activeClass}`}>
            {icon}
            {label} 
            {count !== undefined && <span className={`bg-white px-1.5 py-0.5 rounded-full text-xs opacity-80 border border-${color}-200`}>{count}</span>}
        </button>
    );
};

// --- PRELOADER COMPONENT ---
const Preloader = () => (
    <div className="fixed inset-0 bg-white z-[100] flex flex-col items-center justify-center animate-out fade-out duration-500 fill-mode-forwards" style={{animationDelay: '1.5s', pointerEvents: 'none'}}>
        <div className="relative mb-4">
            <Instagram size={64} className="text-purple-600 animate-bounce" />
            <div className="absolute -bottom-2 left-1/2 -translate-x-1/2 w-12 h-1 bg-black/10 rounded-full blur-sm animate-pulse"></div>
        </div>
        <h1 className="text-2xl font-bold bg-clip-text text-transparent bg-gradient-to-r from-purple-600 to-pink-600 animate-pulse">
            InstaMonitor Pro
        </h1>
    </div>
);

export default function App() {
  // FIX: Prüfe beim Start, ob wir schon eingeloggt waren (localStorage)
  const [isAuthenticated, setIsAuthenticated] = useState(() => {
      return localStorage.getItem('insta_auth') === 'true';
  });
  const [password, setPassword] = useState("");
  const [loginError, setLoginError] = useState(false);
  const [appReady, setAppReady] = useState(false); 
  
  // Auth Check beim Start
  useEffect(() => {
      const loggedIn = localStorage.getItem('isLoggedIn') === 'true';
      if (loggedIn) {
          setIsAuthenticated(true);
      }
      // App ist "bereit" (Preloader weg), sobald wir wissen, ob eingeloggt oder nicht
      // Aber wir wollen Preloader nur zeigen, wenn wir daten laden?
      // Ne, Preloader weg, sobald wir wissen was Phase ist.
      // Wenn eingeloggt -> loadData kümmert sich um Preloader-Ende.
      // Wenn NICHT eingeloggt -> sofort Preloader weg.
      if (!loggedIn) {
          setAppReady(true);
      }
  }, []);
  
  // Data
  const [users, setUsers] = useState([]);
  const [targets, setTargets] = useState([]);
  const [loading, setLoading] = useState(false);
  
  // UI State
  const [activeTab, setActiveTab] = useState('unfiltered'); 
  const [filterText, setFilterText] = useState('');
  const [newTarget, setNewTarget] = useState("");
  const [selectedUsers, setSelectedUsers] = useState([]); 
  
  // Sorting
  const [sortConfig, setSortConfig] = useState({ key: 'found_date', direction: 'desc' });
  
  // Progress State
  const [activeJob, setActiveJob] = useState(null);
  const [copySuccess, setCopySuccess] = useState(false);

  // --- COLUMN RESIZING ---
  const defaultWidths = {
      select: 50,
      user: 250,
      actions: 180,
      bio: 350,
      follower: 120,
      date: 120
  };

  const [colWidths, setColWidths] = useState(() => {
      const saved = localStorage.getItem('instaMonitor_colWidths');
      return saved ? JSON.parse(saved) : defaultWidths;
  });

  const resizingRef = useRef(null);

  const startResize = (e, key) => {
      e.preventDefault();
      resizingRef.current = { key, startX: e.clientX, startWidth: colWidths[key] };
      document.addEventListener('mousemove', handleResizeMove);
      document.addEventListener('mouseup', handleResizeEnd);
  };

  const handleResizeMove = (e) => {
      if (!resizingRef.current) return;
      const { key, startX, startWidth } = resizingRef.current;
      const diff = e.clientX - startX;
      setColWidths(prev => ({ ...prev, [key]: Math.max(50, startWidth + diff) }));
  };

  const handleResizeEnd = () => {
      resizingRef.current = null;
      document.removeEventListener('mousemove', handleResizeMove);
      document.removeEventListener('mouseup', handleResizeEnd);
  };

  useEffect(() => {
      localStorage.setItem('instaMonitor_colWidths', JSON.stringify(colWidths));
  }, [colWidths]);


  // --- STATS ---
  const stats = useMemo(() => {
    return {
        total: users.length,
        unfiltered: users.filter(u => ['new', 'active', 'changed', 'contacted', 'not_found'].includes(u.status)).length,
        favorites: users.filter(u => u.status === 'favorite').length,
        hidden: users.filter(u => u.status === 'hidden').length,
        blocked: users.filter(u => u.status === 'blocked').length,
        email: users.filter(u => u.email).length
    };
  }, [users]);

  // --- LOGIN LOGIC ---
  const handleLogin = async (e) => {
    e.preventDefault();
    setLoginError(false);
    try {
      const res = await fetch(`${API_URL}/login`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ password })
      });
      const data = await res.json();
      if (data.success) {
        setIsAuthenticated(true);
        localStorage.setItem('insta_auth', 'true'); // Session speichern
        loadData();
      } else {
        setLoginError(true);
      }
    } catch (err) {
      console.error(err);
      // Fallback für Local Dev ohne Backend
      if(password === "Tobideno85!") {
          setIsAuthenticated(true);
          localStorage.setItem('insta_auth', 'true');
      } else {
          setLoginError(true);
      }
    }
  };

  const handleLogout = () => {
      setIsAuthenticated(false);
      localStorage.removeItem('insta_auth');
      localStorage.removeItem('isLoggedIn');
      setPassword("");
  };

  // --- DATA LOADING ---
  const loadData = async () => {
    setLoading(true);
    try {
      const res = await fetch(`${API_URL}/users`);
      const data = await res.json();
      setUsers(data.leads || []);
      setTargets(data.targets || []);
    } catch (error) {}
    setLoading(false);
  };

  // Preloader Logic
  useEffect(() => { 
      if (isAuthenticated) {
          loadData().then(() => {
              setTimeout(() => setAppReady(true), 1500); 
          });
      } else {
          setAppReady(true);
      }
  }, [isAuthenticated]);

  // --- POLLING ---
  useEffect(() => {
    let interval;
    if (activeJob && !['finished', 'error'].includes(activeJob.status)) {
      interval = setInterval(async () => {
        try {
          const res = await fetch(`${API_URL}/job-status/${activeJob.username}`);
          const data = await res.json();
          if (data.status) {
            setActiveJob(prev => ({ ...prev, ...data }));
            if (['finished', 'error'].includes(data.status)) {
               loadData(); 
               setTimeout(() => setActiveJob(null), 5000); 
            }
          }
        } catch (e) {}
      }, 1000);
    }
    return () => clearInterval(interval);
  }, [activeJob]);

  // --- ACTIONS ---
  const handleAddTarget = async () => {
    if (!newTarget) return;
    setActiveJob({ username: newTarget, status: 'starting', found: 0, message: 'Startet...' });
    await fetch(`${API_URL}/add-target`, {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({ username: newTarget })
    });
    setNewTarget("");
  };

  const handleSyncSelected = async () => {
    if (selectedUsers.length === 0) return alert("Bitte User auswählen!");
    const usernames = users.filter(u => selectedUsers.includes(u.pk)).map(u => u.username);
    setLoading(true);
    try {
        const res = await fetch(`${API_URL}/sync-users`, {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({ usernames })
        });
        const data = await res.json();
        if (data.success) {
            if(data.job_id) {
                setActiveJob({ username: data.job_id, status: 'running', found: 0, message: 'Startet...' });
                setSelectedUsers([]);
            } else {
                await loadData();
                alert(`Sync fertig: ${data.message}`);
                setSelectedUsers([]);
            }
        }
    } catch (e) { alert("Fehler beim Sync."); } 
    finally { setLoading(false); }
  };

  const handleDeleteSelected = async () => {
    if (selectedUsers.length === 0) return;
    if (!window.confirm(`Wirklich ${selectedUsers.length} User endgültig löschen?`)) return;
    await fetch(`${API_URL}/delete-users`, {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({ pks: selectedUsers })
    });
    setSelectedUsers([]);
    loadData();
  };

  const handleMarkExported = async (usernames) => {
    await fetch(`${API_URL}/mark-exported`, {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({ usernames })
    });
    loadData(); 
  };

  const handleManualAdd = async (username) => {
    if (!username) return;
    setLoading(true); 
    try {
        const res = await fetch(`${API_URL}/add-lead`, {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({ username })
        });
        const data = await res.json();
        if (data.success) {
            alert(`Erfolg: ${data.message}`);
            setNewTarget("");
            loadData(); 
        } else {
            alert(`Fehler: ${data.error || "Unbekannt"}`);
        }
    } catch (e) { alert("Verbindungsfehler."); } 
    finally { setLoading(false); }
  };

  const handleStatusChange = async (pk, newStatus) => {
    setUsers(users.map(u => u.pk === pk ? {...u, status: newStatus} : u));
    await fetch(`${API_URL}/lead/update-status`, {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({ pk, status: newStatus })
    });
  };

  const handleGoToExport = () => {
    setActiveTab('export');
  };

  // --- SORTING ---
  const requestSort = (key) => {
    let direction = 'asc';
    if (sortConfig.key === key && sortConfig.direction === 'asc') direction = 'desc';
    setSortConfig({ key, direction });
  };

  // --- FILTERED DATA ---
  const processedUsers = useMemo(() => {
    let filtered = users;

    switch (activeTab) {
        case 'review': 
        case 'unfiltered':
            filtered = filtered.filter(u => ['new', 'active', 'changed', 'contacted', 'not_found'].includes(u.status));
            break;
        case 'favorites': filtered = filtered.filter(u => u.status === 'favorite'); break;
        case 'hidden': filtered = filtered.filter(u => u.status === 'hidden'); break;
        case 'blocked': filtered = filtered.filter(u => u.status === 'blocked'); break;
        case 'email': filtered = filtered.filter(u => u.email && u.status !== 'blocked' && u.status !== 'hidden'); break;
        case 'export':
            if (selectedUsers.length > 0) filtered = filtered.filter(u => selectedUsers.includes(u.pk));
            else filtered = []; 
            break;
    }

    if (filterText) {
        const lower = filterText.toLowerCase();
        filtered = filtered.filter(u => 
            (u.username||'').toLowerCase().includes(lower) || 
            (u.bio||'').toLowerCase().includes(lower) ||
            (u.fullName||'').toLowerCase().includes(lower)
        );
    }

    return [...filtered].sort((a, b) => {
        let aVal = a[sortConfig.key];
        let bVal = b[sortConfig.key];
        if (aVal == null) aVal = ""; if (bVal == null) bVal = "";
        if (typeof aVal === 'string') aVal = aVal.toLowerCase();
        if (typeof bVal === 'string') bVal = bVal.toLowerCase();
        if (aVal < bVal) return sortConfig.direction === 'asc' ? -1 : 1;
        if (aVal > bVal) return sortConfig.direction === 'asc' ? 1 : -1;
        return 0;
    });
  }, [users, activeTab, filterText, sortConfig, selectedUsers]);

  // --- SELECTION ---
  const toggleSelectAll = () => {
    if (selectedUsers.length === processedUsers.length) setSelectedUsers([]);
    else setSelectedUsers(processedUsers.map(u => u.pk));
  };

  const toggleSelectUser = (pk) => {
    if (selectedUsers.includes(pk)) setSelectedUsers(selectedUsers.filter(id => id !== pk));
    else setSelectedUsers([...selectedUsers, pk]);
  };

  // --- SHORTCUTS ---
  useEffect(() => {
    if (activeTab !== 'review' || processedUsers.length === 0) return;
    const handleKeyDown = (e) => {
        const currentUser = processedUsers[0];
        if (!currentUser) return;
        if (e.key === 'ArrowRight') handleStatusChange(currentUser.pk, 'favorite');
        if (e.key === 'ArrowLeft') handleStatusChange(currentUser.pk, 'blocked');
        if (e.key === 'ArrowDown') handleStatusChange(currentUser.pk, 'hidden');
    };
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [activeTab, processedUsers]);

  const ResizeHandle = ({ id }) => (
      <div 
        className="absolute right-0 top-0 bottom-0 w-2 cursor-col-resize hover:bg-purple-400 group flex items-center justify-center z-10 opacity-0 hover:opacity-100"
        onMouseDown={(e) => startResize(e, id)}
      >
          <div className="w-[1px] h-full bg-purple-500"></div>
      </div>
  );

  // --- LOGIN SCREEN ---
  if (!isAuthenticated) {
    return (
      <div className="min-h-screen bg-slate-900 flex items-center justify-center p-4">
        <div className="bg-white p-8 rounded-2xl shadow-2xl w-full max-w-md animate-in fade-in zoom-in duration-300">
          <div className="flex justify-center mb-6">
            <div className="bg-purple-600 p-4 rounded-full text-white shadow-lg shadow-purple-500/30">
              <Lock size={32} />
            </div>
          </div>
          <h2 className="text-2xl font-bold text-center mb-2 text-slate-800">InstaMonitor Pro</h2>
          <p className="text-center text-slate-500 mb-6 text-sm">Bitte authentifizieren</p>
          
          <form onSubmit={handleLogin} className="space-y-4">
            <div>
                <input 
                  type="password" 
                  className={`w-full px-4 py-3 border rounded-lg focus:ring-2 outline-none transition-all ${loginError ? 'border-red-500 focus:ring-red-200' : 'border-slate-300 focus:ring-purple-200 focus:border-purple-500'}`}
                  placeholder="Passwort eingeben..."
                  value={password}
                  onChange={e => {setPassword(e.target.value); setLoginError(false);}}
                  autoFocus
                />
                {loginError && <p className="text-red-500 text-xs mt-1 ml-1 flex items-center gap-1"><AlertCircle size={10}/> Falsches Passwort</p>}
            </div>
            <button className="w-full bg-gradient-to-r from-purple-600 to-indigo-600 hover:from-purple-700 hover:to-indigo-700 text-white font-bold py-3 rounded-lg transition-all shadow-md transform hover:scale-[1.02] active:scale-[0.98]">
              Zugriff anfordern
            </button>
          </form>
          <div className="mt-6 text-center text-slate-300 text-xs">
              Protected System • v2.0
          </div>
        </div>
      </div>
    );
  }

  // --- RENDER ---
  return (
    <div className="min-h-screen bg-slate-50 text-slate-800 font-sans" style={{ cursor: resizingRef.current ? 'col-resize' : 'auto' }}>
      
      {!appReady && <Preloader />}

      {/* HEADER */}
      <nav className="bg-white border-b border-slate-200 sticky top-0 z-30 px-4 md:px-6 py-4 flex flex-col md:flex-row items-center justify-between shadow-sm gap-4">
        <div className="flex items-center gap-2">
          <Instagram className="text-purple-600" size={28} />
          <h1 className="text-xl font-bold bg-clip-text text-transparent bg-gradient-to-r from-purple-600 to-pink-600">InstaMonitor</h1>
        </div>
        
        {/* TAB BAR (Responsive Scroll) */}
        <div className="flex gap-2 bg-slate-50 p-1.5 rounded-xl border border-slate-200 overflow-x-auto w-full md:w-auto no-scrollbar">
            <TabButton active={activeTab === 'review'} onClick={() => setActiveTab('review')} label="Review" color="pink" icon={<Play size={16}/>} />
            <div className="w-[1px] bg-slate-300 mx-1 flex-shrink-0"></div>
            <TabButton active={activeTab === 'unfiltered'} onClick={() => setActiveTab('unfiltered')} label="Ungefiltert" count={stats.unfiltered} color="purple"/>
            <TabButton active={activeTab === 'favorites'} onClick={() => setActiveTab('favorites')} label="Favoriten" count={stats.favorites} color="yellow"/>
            <TabButton active={activeTab === 'email'} onClick={() => setActiveTab('email')} label="Email" count={stats.email} color="blue"/>
            <TabButton active={activeTab === 'hidden'} onClick={() => setActiveTab('hidden')} label="Versteckt" count={stats.hidden} color="slate"/>
            <TabButton active={activeTab === 'blocked'} onClick={() => setActiveTab('blocked')} label="Blockiert" count={stats.blocked} color="red"/>
            <TabButton active={activeTab === 'export'} onClick={() => setActiveTab('export')} label="Export" color="green"/>
            <TabButton active={activeTab === 'add'} onClick={() => setActiveTab('add')} label="+" color="indigo" />
        </div>

        <div className="flex items-center gap-2 w-full md:w-auto">
           <div className="flex bg-slate-100 rounded-lg p-1 flex-1 md:flex-none">
             <input type="text" placeholder="Ziel..." className="bg-transparent px-3 py-1 outline-none text-sm w-full md:w-32" value={newTarget} onChange={e => setNewTarget(e.target.value)} />
             <button onClick={handleAddTarget} className="bg-black text-white p-1.5 rounded-md hover:bg-slate-800"><Plus size={16} /></button>
           </div>
           <button onClick={loadData} className="p-2 hover:bg-slate-100 rounded-full relative z-50" title="Reload"><RefreshCw size={18} /></button>
           <button 
                onClick={handleLogout} 
                className="bg-red-50 hover:bg-red-100 text-red-600 p-2 rounded-full cursor-pointer relative z-50 transition-colors" 
                title="Ausloggen"
           >
               <LogOut size={18}/>
           </button>
        </div>
      </nav>

      <main className="w-full px-4 md:px-8 py-6 space-y-6">
        
        {/* CONTROLS */}
        {activeTab !== 'review' && (
        <div className="flex flex-col md:flex-row justify-between items-center bg-white p-3 rounded-xl shadow-sm border border-slate-200 gap-3">
            <div className="flex flex-col md:flex-row items-center gap-4 w-full md:w-auto">
                <div className="relative w-full md:w-72">
                    <Search size={18} className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" />
                    <input type="text" placeholder="Suchen..." className="w-full pl-10 pr-4 py-2 bg-slate-50 border border-slate-200 rounded-lg text-sm outline-none focus:border-purple-500" value={filterText} onChange={(e) => setFilterText(e.target.value)} />
                </div>
                {selectedUsers.length > 0 && (
                    <div className="flex items-center gap-2 bg-purple-50 px-3 py-1.5 rounded-lg border border-purple-100 animate-in fade-in w-full md:w-auto justify-between md:justify-start">
                        <span className="text-purple-800 text-sm font-bold whitespace-nowrap">{selectedUsers.length} markiert</span>
                        <div className="flex gap-1">
                            <button onClick={handleSyncSelected} className="text-xs bg-purple-600 text-white px-2 py-1 rounded hover:bg-purple-700 flex items-center gap-1">
                                <RefreshCw size={12}/> Sync
                            </button>
                            <button onClick={handleGoToExport} className="text-xs bg-green-600 text-white px-2 py-1 rounded hover:bg-green-700 flex items-center gap-1">
                                <Copy size={12}/> Export
                            </button>
                            <button onClick={handleDeleteSelected} className="text-xs bg-red-600 text-white px-2 py-1 rounded hover:bg-red-700 flex items-center gap-1">
                                <Trash2 size={12}/> Del
                            </button>
                        </div>
                    </div>
                )}
            </div>
            {activeJob && (
                <div className="flex items-center gap-3 bg-blue-50 px-4 py-2 rounded-lg border border-blue-100 w-full md:w-auto">
                    <Loader2 size={18} className="animate-spin text-blue-600"/>
                    <span className="text-sm text-blue-800 font-medium truncate">{activeJob.username}: {activeJob.message}</span>
                </div>
            )}
        </div>
        )}

        {/* --- REVIEW MODE --- */}
        {activeTab === 'add' ? (
            <div className="flex flex-col items-center justify-center min-h-[50vh] bg-white rounded-2xl shadow-sm border border-slate-200 p-6 md:p-12">
                <div className="bg-indigo-100 p-4 rounded-full text-indigo-600 mb-6">
                    <UserPlus size={48} />
                </div>
                <h2 className="text-2xl font-bold text-slate-800 mb-2">Manuell User hinzufügen</h2>
                <p className="text-slate-500 mb-8 text-center max-w-md">
                    Füge hier einen Instagram-Usernamen ein (ohne @).
                </p>
                <div className="flex gap-2 w-full max-w-md">
                    <input 
                        type="text" 
                        placeholder="Instagram Username" 
                        className="flex-1 px-4 py-3 border border-slate-300 rounded-lg outline-none focus:border-indigo-500 focus:ring-2 focus:ring-indigo-200"
                        value={newTarget}
                        onChange={e => setNewTarget(e.target.value)}
                        onKeyDown={e => e.key === 'Enter' && handleManualAdd(newTarget)}
                    />
                    <button 
                        onClick={() => handleManualAdd(newTarget)} 
                        className="bg-indigo-600 hover:bg-indigo-700 text-white px-6 py-3 rounded-lg font-bold"
                    >
                        {loading ? <Loader2 className="animate-spin"/> : "Add"}
                    </button>
                </div>
            </div>
        ) : activeTab === 'review' ? (
            <div className="flex flex-col items-center justify-center min-h-[60vh]">
                {processedUsers.length > 0 ? (
                    <div className="bg-white rounded-2xl shadow-xl border border-slate-200 p-6 w-full max-w-lg text-center relative overflow-hidden">
                        <div className="absolute top-0 left-0 w-full h-2 bg-gradient-to-r from-purple-500 to-pink-500"></div>
                        <div className="absolute top-4 right-4 bg-slate-100 text-slate-500 text-xs px-2 py-1 rounded-full">
                            Src: {processedUsers[0].sourceAccount}
                        </div>

                        <div className="w-24 h-24 bg-slate-200 rounded-full mx-auto flex items-center justify-center text-3xl font-bold text-slate-400 mb-4 mt-4">
                            {processedUsers[0].username[0].toUpperCase()}
                        </div>

                        <a 
                            href={`https://instagram.com/${processedUsers[0].username}`} 
                            target="_blank" 
                            rel="noreferrer" 
                            className="text-2xl font-bold text-slate-800 mb-1 hover:text-purple-600 hover:underline block"
                        >
                            {processedUsers[0].username}
                        </a>
                        
                        <div className="text-slate-500 mb-4 flex flex-col items-center">
                            <span className="text-sm">{processedUsers[0].fullName}</span>
                            <span className="text-blue-600 font-bold mt-1 text-xs bg-blue-50 px-3 py-1 rounded-full border border-blue-100">
                                {processedUsers[0].followersCount?.toLocaleString()} Follower
                            </span>
                        </div>

                        {/* TOP ACTION BUTTONS */}
                        <div className="flex justify-center gap-3 mb-6">
                            <button onClick={() => handleStatusChange(processedUsers[0].pk, 'blocked')} className="flex flex-col items-center gap-1 p-2 rounded-xl bg-red-50 text-red-600 border border-red-200 hover:bg-red-100 w-20" title="Block">
                                <Ban size={24}/> <span className="font-bold text-[10px]">BLOCK</span>
                            </button>
                            <button onClick={() => handleStatusChange(processedUsers[0].pk, 'hidden')} className="flex flex-col items-center gap-1 p-2 rounded-xl bg-slate-100 text-slate-600 border border-slate-200 hover:bg-slate-200 w-20" title="Hide">
                                <EyeOff size={24}/> <span className="font-bold text-[10px]">HIDE</span>
                            </button>
                            <button onClick={() => handleStatusChange(processedUsers[0].pk, 'favorite')} className="flex flex-col items-center gap-1 p-2 rounded-xl bg-yellow-100 text-yellow-600 border border-yellow-200 hover:bg-yellow-200 w-20" title="Fav">
                                <Heart size={24} className="fill-yellow-600"/> <span className="font-bold text-[10px]">FAV</span>
                            </button>
                        </div>

                        <div className="bg-slate-50 p-6 rounded-xl border border-slate-100 mb-6 text-center">
                            <p className="whitespace-pre-wrap text-slate-700 italic text-sm leading-relaxed mb-4 max-h-40 overflow-y-auto">{processedUsers[0].bio || "-"}</p>
                            
                            {processedUsers[0].externalUrl && (
                                <a 
                                    href={processedUsers[0].externalUrl} 
                                    target="_blank" 
                                    rel="noreferrer" 
                                    className="inline-flex items-center gap-1 text-blue-600 font-bold bg-blue-50 px-4 py-2 rounded-full text-sm hover:underline mb-2 border border-blue-100"
                                >
                                    <Globe size={16}/> Link öffnen: <span className="underline">{processedUsers[0].externalUrl.replace(/^https?:\/\//, '')}</span>
                                </a>
                            )}
                            
                            <div className="flex justify-center mt-4">
                                <a href={`https://instagram.com/${processedUsers[0].username}`} target="_blank" rel="noreferrer" className="flex items-center gap-2 bg-gradient-to-r from-purple-600 to-pink-600 text-white px-6 py-2 rounded-full text-sm font-bold hover:opacity-90 shadow-md">
                                    <Instagram size={18}/> Profil öffnen
                                </a>
                            </div>
                        </div>
                    </div>
                ) : (
                    <div className="text-center p-12 bg-white rounded-2xl shadow-sm border border-slate-200">
                        <div className="text-4xl mb-4">🎉</div>
                        <h2 className="text-xl font-bold text-slate-800 mb-2">Alles erledigt!</h2>
                        <button onClick={() => setActiveTab('favorites')} className="mt-4 text-purple-600 font-bold hover:underline">Zu Favoriten</button>
                    </div>
                )}
            </div>
        ) : activeTab === 'export' ? (
            <div className="bg-white p-6 md:p-8 rounded-xl shadow-sm border border-slate-200">
                <h2 className="text-xl font-bold mb-4 flex items-center gap-2"><Copy size={24}/> Export</h2>
                <textarea readOnly className="w-full h-64 p-4 bg-slate-50 border border-slate-200 rounded-lg font-mono text-sm focus:outline-none" value={processedUsers.map(u => u.username).join('\n')} />
                <div className="mt-4 flex gap-3 flex-wrap">
                    <button onClick={() => {
                            navigator.clipboard.writeText(processedUsers.map(u => u.username).join('\n'));
                            setCopySuccess(true); setTimeout(() => setCopySuccess(false), 2000);
                            handleMarkExported(processedUsers.map(u => u.username));
                        }} className="bg-green-600 hover:bg-green-700 text-white px-6 py-2 rounded-lg font-bold flex items-center gap-2" disabled={processedUsers.length === 0}>
                        {copySuccess ? <Check size={20}/> : <Copy size={20}/>} Kopieren
                    </button>
                    <button onClick={() => setSelectedUsers([])} className="bg-slate-200 hover:bg-slate-300 text-slate-700 px-6 py-2 rounded-lg font-bold flex items-center gap-2" disabled={selectedUsers.length === 0}>
                        <Trash2 size={20}/> Leeren
                    </button>
                </div>
            </div>
        ) : (
            // TABLE VIEW (Mobile Card / Desktop Table)
            <div className="bg-white rounded-xl shadow-sm border border-slate-200 overflow-x-auto relative">
                
                {/* Mobile View (Cards) */}
                <div className="md:hidden space-y-4 p-4">
                    {processedUsers.map((user) => {
                        const isSelected = selectedUsers.includes(user.pk);
                        return (
                            <div key={user.pk} className={`border rounded-lg p-4 shadow-sm ${isSelected ? 'bg-purple-50 border-purple-200' : 'bg-white'}`}>
                                <div className="flex justify-between items-start mb-2">
                                    <div className="flex items-center gap-3">
                                        <input type="checkbox" checked={isSelected} onChange={() => toggleSelectUser(user.pk)} className="w-5 h-5 rounded accent-purple-600"/>
                                        <div className="font-bold text-lg">{user.username}</div>
                                    </div>
                                    <div className="flex gap-1">
                                        <button onClick={() => handleStatusChange(user.pk, user.status === 'favorite' ? 'active' : 'favorite')} className="p-2 bg-white border rounded text-yellow-500"><Heart size={16} className={user.status === 'favorite' ? 'fill-yellow-500' : ''}/></button>
                                        <button onClick={() => handleStatusChange(user.pk, 'blocked')} className="p-2 bg-white border rounded text-red-500"><Ban size={16}/></button>
                                    </div>
                                </div>
                                <div className="text-sm text-slate-600 mb-2 whitespace-pre-wrap line-clamp-3">{user.bio}</div>
                                {user.externalUrl && <a href={user.externalUrl} target="_blank" className="text-blue-600 text-xs block mb-1 truncate"><Globe size={12} className="inline"/> Link</a>}
                                    <div className="flex justify-between items-center text-xs text-slate-400 mt-3 border-t pt-2">
                                    <span>{user.followersCount?.toLocaleString()} Follower</span>
                                    <span>{formatDate(user.foundDate)}</span>
                                </div>
                            </div>
                        )
                    })}
                </div>

                {/* Desktop Table */}
                <table className="w-full text-left table-fixed hidden md:table">
                    <thead className="bg-slate-50 text-slate-500 font-bold border-b border-slate-200 uppercase tracking-wider text-sm">
                        <tr>
                            <th className="p-4 relative w-12"><input type="checkbox" checked={selectedUsers.length === processedUsers.length && processedUsers.length > 0} onChange={toggleSelectAll} className="w-4 h-4 rounded accent-purple-600"/><ResizeHandle id="select"/></th>
                            <th className="p-4 relative hover:bg-slate-100" style={{ width: colWidths.user }}>User <ResizeHandle id="user"/></th>
                            <th className="p-4 relative" style={{ width: colWidths.actions }}>Aktionen <ResizeHandle id="actions"/></th>
                            <th className="p-4 relative" style={{ width: colWidths.bio }}>Bio <ResizeHandle id="bio"/></th>
                            <th className="p-4 relative hover:bg-slate-100" style={{ width: colWidths.follower }}>Follower <ResizeHandle id="follower"/></th>
                            <th className="p-4 relative hover:bg-slate-100" style={{ width: colWidths.date }}>Datum <ResizeHandle id="date"/></th>
                        </tr>
                    </thead>
                    <tbody className="divide-y divide-slate-100 text-base">
                        {processedUsers.map((user) => {
                            const isSelected = selectedUsers.includes(user.pk);
                            const isFavorite = user.status === 'favorite';
                            return (
                                <tr key={user.pk} className={`group transition-colors ${isSelected ? 'bg-purple-50' : 'hover:bg-slate-50'} ${isFavorite ? 'bg-yellow-50' : ''}`}>
                                    <td className="p-4 align-top"><input type="checkbox" checked={isSelected} onChange={() => toggleSelectUser(user.pk)} className="w-4 h-4 rounded accent-purple-600 mt-2"/></td>
                                    
                                    <td className="p-4 align-top overflow-hidden">
                                        <div className="flex items-center gap-3">
                                            <div className="w-10 h-10 rounded-full bg-slate-200 flex-shrink-0 flex items-center justify-center font-bold text-slate-500 text-sm">{user.username[0].toUpperCase()}</div>
                                            <div className="min-w-0">
                                                <a href={`https://instagram.com/${user.username}`} target="_blank" className="font-bold text-lg text-slate-900 hover:text-purple-600 hover:underline block truncate">{user.username}</a>
                                                <div className="text-xs text-slate-400 truncate">{user.fullName}</div>
                                                <div className="text-[10px] text-slate-300 mt-0.5 truncate">Src: {user.sourceAccount}</div>
                                                {user.status === 'new' && <span className="inline-block mt-1 bg-purple-600 text-white text-[10px] px-1.5 rounded">NEU</span>}
                                            </div>
                                        </div>
                                    </td>

                                    <td className="p-4 align-top">
                                        <div className="flex flex-wrap gap-2">
                                            <button onClick={() => handleStatusChange(user.pk, user.status === 'favorite' ? 'active' : 'favorite')} className={`p-2 rounded-lg border shadow-sm transition-colors ${user.status === 'favorite' ? 'bg-yellow-400 border-yellow-500 text-white' : 'bg-white border-slate-200 text-slate-400 hover:bg-yellow-50 hover:text-yellow-500'}`} title="Favorit">
                                                <Heart size={18} className={user.status === 'favorite' ? 'fill-white' : ''}/>
                                            </button>
                                            <button onClick={() => handleStatusChange(user.pk, 'blocked')} className="p-2 bg-white border border-slate-200 rounded-lg shadow-sm text-slate-400 hover:bg-red-50 hover:text-red-600 hover:border-red-200" title="Blockieren"><Ban size={18}/></button>
                                            <button onClick={() => handleStatusChange(user.pk, user.status === 'hidden' ? 'active' : 'hidden')} className="p-2 bg-white border border-slate-200 rounded-lg shadow-sm text-slate-400 hover:bg-slate-100 hover:text-slate-600" title={user.status === 'hidden' ? 'Anzeigen' : 'Verstecken'}>
                                                {user.status === 'hidden' ? <EyeOff size={18}/> : <EyeOff size={18} className="opacity-50"/>}
                                            </button>
                                        </div>
                                    </td>

                                    <td className="p-4 align-top">
                                        {user.status === 'changed' && <div className="mb-1 text-xs bg-blue-100 text-blue-700 px-2 py-0.5 rounded inline-block">Update: {user.changeDetails}</div>}
                                        <div className="text-slate-600 text-sm whitespace-pre-wrap break-words">{user.bio}</div>
                                        {user.externalUrl && (
                                            <a href={user.externalUrl} target="_blank" rel="noreferrer" className="mt-2 flex items-center gap-1 text-blue-600 font-bold text-xs hover:underline bg-blue-50 px-2 py-1 rounded w-fit max-w-full truncate">
                                                <Globe size={12}/> {user.externalUrl.replace(/^https?:\/\//, '')}
                                            </a>
                                        )}
                                        {user.email && <div className="mt-2 flex items-center gap-1 text-purple-700 font-bold text-xs"><Mail size={12}/> {user.email}</div>}
                                    </td>

                                    <td className="p-4 align-top">
                                        <div className="font-bold text-blue-600">{user.followersCount?.toLocaleString()}</div>
                                    </td>

                                    <td className="p-4 align-top text-xs text-slate-500">
                                        <div>{formatDate(user.foundDate)}</div>
                                        {user.lastExported && <div className="text-green-600 mt-1">Exp: {formatDate(user.lastExported)}</div>}
                                    </td>
                                </tr>
                            );
                        })}
                    </tbody>
                </table>
            </div>
        )}
      </main>
    </div>
  );
}