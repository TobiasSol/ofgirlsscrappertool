import React, { useState, useEffect, useMemo } from 'react';
import { 
  Search, Users, RefreshCw, Trash2, Mail, Instagram, 
  CheckCircle, AlertCircle, Calendar, Plus, Lock, EyeOff, Activity, ArrowUpDown, XCircle, Loader2, Ban, Heart
} from 'lucide-react';

const API_URL = "http://localhost:5000/api"; 

// --- HELPER: Datum formatieren (DD.MM.YYYY) ---
const formatDate = (isoString) => {
  if (!isoString) return "-";
  try {
    const date = new Date(isoString);
    return date.toLocaleDateString('de-DE', {
      day: '2-digit', month: '2-digit', year: 'numeric'
    });
  } catch (e) { return isoString; }
};

export default function App() {
  const [isAuthenticated, setIsAuthenticated] = useState(true); // Passwortschutz deaktiviert
  const [password, setPassword] = useState("");
  
  // Data
  const [users, setUsers] = useState([]);
  const [targets, setTargets] = useState([]);
  const [loading, setLoading] = useState(false);
  
  // UI State
  const [filterText, setFilterText] = useState('');
  const [showHidden, setShowHidden] = useState(false);
  const [showBlocked, setShowBlocked] = useState(false);
  const [showFavorites, setShowFavorites] = useState(false);
  const [onlyEmail, setOnlyEmail] = useState(false);
  const [newTarget, setNewTarget] = useState("");
  
  // Sorting
  const [sortConfig, setSortConfig] = useState({ key: 'found_date', direction: 'desc' });
  
  // Progress State
  const [activeJob, setActiveJob] = useState(null); // { username: '...', status: '...', found: 0, message: '...' }

  // Stats
  const stats = useMemo(() => {
    const active = users.filter(u => u.status !== 'hidden');
    return {
        total: active.length,
        withEmail: active.filter(u => u.email).length,
        new: active.filter(u => u.status === 'new').length
    };
  }, [users]);

  // --- SORTIER LOGIK ---
  const requestSort = (key) => {
    let direction = 'asc';
    if (sortConfig.key === key && sortConfig.direction === 'asc') {
      direction = 'desc';
    }
    setSortConfig({ key, direction });
  };

  const sortData = (data) => {
    if (!sortConfig.key) return data;
    
    return [...data].sort((a, b) => {
      let aVal = a[sortConfig.key];
      let bVal = b[sortConfig.key];
      
      // Spezielle Behandlung für Zahlen & Strings
      if (typeof aVal === 'string') aVal = aVal.toLowerCase();
      if (typeof bVal === 'string') bVal = bVal.toLowerCase();
      
      if (aVal < bVal) return sortConfig.direction === 'asc' ? -1 : 1;
      if (aVal > bVal) return sortConfig.direction === 'asc' ? 1 : -1;
      return 0;
    });
  };

  // --- POLLING FÜR PROGRESS ---
  useEffect(() => {
    let interval;
    if (activeJob && activeJob.status !== 'finished' && activeJob.status !== 'error') {
      interval = setInterval(async () => {
        try {
          const res = await fetch(`${API_URL}/job-status/${activeJob.username}`);
          const data = await res.json();
          if (data.status) {
            setActiveJob(prev => ({ ...prev, ...data }));
            if (data.status === 'finished' || data.status === 'error') {
               loadData(); // Wenn fertig, Daten neu laden
               setTimeout(() => setActiveJob(null), 5000); // Nach 5s ausblenden
            }
          }
        } catch (e) { console.error("Polling error", e); }
      }, 1000);
    }
    return () => clearInterval(interval);
  }, [activeJob]);

  // --- AUTO LOAD DATA ON LOGIN ---
  useEffect(() => {
    if (isAuthenticated) {
        loadData();
    }
  }, [isAuthenticated]);

  // --- DATA LOADING & ACTIONS ---
  const handleLogin = async (e) => {
    e.preventDefault();
    try {
        const res = await fetch(`${API_URL}/login`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ password })
        });
        const data = await res.json();
        if (data.success) { setIsAuthenticated(true); loadData(); }
        else { alert("Falsches Passwort!"); }
    } catch (err) { if(password === "Tobideno85!") setIsAuthenticated(true); }
  };

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

  const handleSync = async () => {
    await fetch(`${API_URL}/sync`, { method: 'POST' });
    alert("Sync gestartet! Prüfe im Hintergrund...");
  };

  const toggleFavorite = async (pk, currentStatus) => {
    // Toggle: Wenn Favorit -> Active, sonst -> Favorite
    const newStatus = currentStatus === 'favorite' ? 'active' : 'favorite';
    await updateStatus(pk, newStatus);
  };

  const toggleHideUser = async (pk, currentStatus) => {
    // Wenn aktuell hidden -> wieder active (contacted)
    // Wenn active -> hidden
    const newStatus = currentStatus === 'hidden' ? 'contacted' : 'hidden';
    await updateStatus(pk, newStatus);
  };

  const blockUser = async (pk) => {
    // Sofort blockieren ohne Nachfrage
    await updateStatus(pk, 'blocked');
  };

  const updateStatus = async (pk, status) => {
    setUsers(users.map(u => u.pk === pk ? {...u, status: status} : u));
    await fetch(`${API_URL}/lead/update-status`, {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({ pk, status })
    });
  };

  // --- FILTER & SORT ---
  const processedUsers = useMemo(() => {
    let filtered = users.filter(user => {
      // Blocked Logic
      if (user.status === 'blocked' && !showBlocked) return false;
      if (user.status !== 'blocked' && showBlocked) return false; 
      
      // Favorite Logic
      if (showFavorites) {
          // Wenn Filter AN: Zeige NUR Favoriten
          if (user.status !== 'favorite') return false;
      } else {
          // Wenn Filter AUS: Verstecke Favoriten (standardmäßig ausgeblendet wie Hidden)
          if (user.status === 'favorite') return false;
      }

      // Hidden Logic
      if (!showHidden && !showBlocked && !showFavorites && user.status === 'hidden') return false;
      
      if (onlyEmail && !user.email) return false;
      
      const searchContent = ((user.username||'')+(user.bio||'')+(user.full_name||'')).toLowerCase();
      return searchContent.includes(filterText.toLowerCase());
    });
    
    return sortData(filtered);
  }, [users, filterText, showHidden, showBlocked, showFavorites, onlyEmail, sortConfig]);

  // --- LOGIN SCREEN ---
  if (!isAuthenticated) {
    return (
      <div className="min-h-screen bg-slate-900 flex items-center justify-center p-4">
        <div className="bg-white p-8 rounded-2xl shadow-2xl w-full max-w-md">
           <div className="flex justify-center mb-6"><div className="bg-purple-600 p-3 rounded-full text-white"><Lock size={32} /></div></div>
           <h2 className="text-2xl font-bold text-center mb-6 text-slate-800">InstaMonitor Zugriff</h2>
           <form onSubmit={handleLogin} className="space-y-4">
             <input type="password" className="w-full px-4 py-3 border border-slate-300 rounded-lg focus:ring-2 focus:ring-purple-500 outline-none" placeholder="Passwort..." value={password} onChange={e => setPassword(e.target.value)}/>
             <button className="w-full bg-purple-600 hover:bg-purple-700 text-white font-bold py-3 rounded-lg">Login</button>
           </form>
        </div>
      </div>
    );
  }

  // --- DASHBOARD ---
  return (
    <div className="min-h-screen bg-slate-50 text-slate-800 font-sans">
      <nav className="bg-white border-b border-slate-200 sticky top-0 z-20 px-6 py-4 flex flex-col md:flex-row items-center justify-between shadow-sm gap-4">
        <div className="flex items-center gap-2">
          <Instagram className="text-purple-600" size={28} />
          <h1 className="text-2xl font-bold bg-clip-text text-transparent bg-gradient-to-r from-purple-600 to-pink-600">InstaMonitor Pro</h1>
        </div>
        
        <div className="flex items-center gap-3">
           <div className="flex bg-slate-100 rounded-lg p-1">
             <input type="text" placeholder="Neues Ziel..." className="bg-transparent px-3 py-2 outline-none text-base w-48" value={newTarget} onChange={e => setNewTarget(e.target.value)} />
             <button onClick={handleAddTarget} className="bg-black text-white p-2 rounded-md hover:bg-slate-800"><Plus size={20} /></button>
           </div>
           <button onClick={handleSync} className="flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-bold bg-purple-100 text-purple-700 hover:bg-purple-200">
             <RefreshCw size={18}/> Sync Check
           </button>
           <button onClick={loadData} className="p-2 hover:bg-slate-100 rounded-full"><RefreshCw size={20} /></button>
        </div>
      </nav>

      <main className="w-full px-8 py-6 space-y-6">
        
        {/* STATS */}
        <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
            <div className="bg-white p-6 rounded-xl shadow-sm border border-slate-200">
                <div className="text-slate-500 text-sm font-bold uppercase">Aktive Leads</div>
                <div className="text-4xl font-bold mt-2">{stats.total}</div>
            </div>
            <div className="bg-white p-6 rounded-xl shadow-sm border border-slate-200">
                <div className="text-slate-500 text-sm font-bold uppercase">Mit Email</div>
                <div className="text-4xl font-bold mt-2 text-green-600">{stats.withEmail}</div>
            </div>
            <div className="bg-gradient-to-br from-purple-600 to-indigo-600 p-6 rounded-xl shadow-md text-white">
                <div className="text-indigo-100 text-sm font-bold uppercase">Neue Funde</div>
                <div className="text-4xl font-bold mt-2">{stats.new}</div>
            </div>
        </div>

        {/* PROGRESS BAR (Wenn Job aktiv) */}
        {activeJob && (
            <div className="bg-blue-50 border border-blue-200 p-4 rounded-xl flex items-center gap-4 animate-in fade-in slide-in-from-top-4">
                <div className="bg-blue-600 p-2 rounded-full text-white"><Loader2 size={24} className="animate-spin"/></div>
                <div className="flex-1">
                    <div className="font-bold text-blue-900">Scrape läuft: {activeJob.username}</div>
                    <div className="text-blue-700 text-sm">{activeJob.message}</div>
                </div>
                <div className="text-2xl font-bold text-blue-800">{activeJob.found} Leads</div>
            </div>
        )}

        {/* CONTROLS */}
        <div className="flex flex-col md:flex-row justify-between items-center bg-white p-4 rounded-xl shadow-sm border border-slate-200 gap-4">
            <div className="relative w-full md:w-96">
                <Search size={20} className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" />
                <input type="text" placeholder="Suche..." className="w-full pl-10 pr-4 py-2 bg-slate-50 border border-slate-200 rounded-lg text-base focus:border-purple-500 outline-none" value={filterText} onChange={(e) => setFilterText(e.target.value)} />
            </div>
            <div className="flex items-center gap-4">
                <label className="flex items-center gap-2 text-sm font-bold text-slate-700 cursor-pointer bg-slate-50 px-4 py-2 rounded-lg hover:bg-slate-100"><input type="checkbox" checked={onlyEmail} onChange={e => setOnlyEmail(e.target.checked)} className="accent-purple-600"/> <Mail size={18} className={onlyEmail ? "text-purple-600" : "text-slate-400"}/> Nur mit Email</label>
                <label className="flex items-center gap-2 text-sm font-bold text-yellow-700 cursor-pointer bg-yellow-50 px-4 py-2 rounded-lg hover:bg-yellow-100"><input type="checkbox" checked={showFavorites} onChange={e => {setShowFavorites(e.target.checked); setShowHidden(false); setShowBlocked(false)}} className="accent-yellow-500"/> <Heart size={18} className={showFavorites ? "fill-yellow-500 text-yellow-500" : "text-yellow-400"}/> Favoriten</label>
                <label className="flex items-center gap-2 text-sm font-bold text-slate-700 cursor-pointer bg-slate-50 px-4 py-2 rounded-lg hover:bg-slate-100"><input type="checkbox" checked={showHidden} onChange={e => {setShowHidden(e.target.checked); setShowBlocked(false); setShowFavorites(false)}} className="accent-purple-600"/> <EyeOff size={18} className={showHidden ? "text-slate-800" : "text-slate-400"}/> Versteckte</label>
                <label className="flex items-center gap-2 text-sm font-bold text-red-700 cursor-pointer bg-red-50 px-4 py-2 rounded-lg hover:bg-red-100"><input type="checkbox" checked={showBlocked} onChange={e => {setShowBlocked(e.target.checked); setShowHidden(false); setShowFavorites(false)}} className="accent-red-600"/> <Ban size={18} className={showBlocked ? "text-red-800" : "text-red-400"}/> Blockierte</label>
            </div>
        </div>

        {/* TABLE */}
        <div className="bg-white rounded-xl shadow-sm border border-slate-200 overflow-hidden">
          <table className="w-full text-left">
            <thead className="bg-slate-50 text-slate-500 font-bold border-b border-slate-200 uppercase tracking-wider text-sm">
              <tr>
                <th className="p-6 cursor-pointer hover:bg-slate-100" onClick={() => requestSort('username')}>User <ArrowUpDown size={14} className="inline opacity-50"/></th>
                <th className="p-6 min-w-[180px]">Aktionen</th>
                <th className="p-6 w-1/3">Bio & Email</th>
                <th className="p-6 cursor-pointer hover:bg-slate-100" onClick={() => requestSort('followers_count')}>Follower <ArrowUpDown size={14} className="inline opacity-50"/></th>
                <th className="p-6 cursor-pointer hover:bg-slate-100" onClick={() => requestSort('found_date')}>Datum <ArrowUpDown size={14} className="inline opacity-50"/></th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100 text-base">
              {processedUsers.map((user) => {
                const isFavorite = user.status === 'favorite';
                const isChanged = user.status === 'changed';
                const isHidden = user.status === 'hidden';
                const isNotFound = user.status === 'not_found';
                
                return (
                  <tr key={user.pk} className={`group transition-colors 
                    ${isChanged ? 'bg-blue-50' : ''} 
                    ${isFavorite ? 'bg-yellow-100 border-l-4 border-yellow-400' : ''}
                    ${isHidden ? 'bg-slate-100 opacity-50 grayscale' : ''}
                    ${isNotFound ? 'bg-red-50' : 'hover:bg-slate-50'}
                  `}>
                    <td className="p-6 align-top">
                      <div className="flex items-start gap-4">
                        <div className={`w-12 h-12 rounded-full flex items-center justify-center font-bold text-lg text-white ${isNotFound ? 'bg-red-400' : 'bg-slate-300'}`}>
                            {user.username[0].toUpperCase()}
                        </div>
                        <div>
                          <div className="font-bold text-lg text-slate-900 flex items-center gap-2">
                            <a href={`https://instagram.com/${user.username}`} target="_blank" className="hover:text-purple-600 hover:underline">{user.username}</a>
                            {user.status === 'new' && <span className="bg-purple-600 text-white text-xs px-2 py-0.5 rounded">NEU</span>}
                            {isNotFound && <span className="bg-red-600 text-white text-xs px-2 py-0.5 rounded flex items-center gap-1"><XCircle size={12}/> GELÖSCHT</span>}
                          </div>
                          <div className="text-slate-500 font-medium">{user.full_name}</div>
                          {user.is_private === 1 && <div className="text-xs text-slate-400 flex items-center gap-1 mt-1"><Lock size={12}/> Privat</div>}
                        </div>
                      </div>
                    </td>
                    <td className="p-6 align-top">
                      <div className="flex gap-2"> 
                         {/* Favorite Button */}
                         <button onClick={() => toggleFavorite(user.pk, user.status)} className={`p-2 border rounded-lg shadow-sm transition-colors ${user.status === 'favorite' ? 'bg-yellow-100 border-yellow-300 text-yellow-600' : 'bg-white border-slate-200 text-slate-400 hover:text-yellow-500'}`} title="Favorit">
                            <Heart size={20} className={user.status === 'favorite' ? 'fill-yellow-500' : ''}/>
                         </button>

                         <a href={`https://instagram.com/${user.username}`} target="_blank" className="p-2 text-slate-400 hover:text-pink-600 bg-white border border-slate-200 rounded-lg shadow-sm"><Instagram size={20} /></a>
                         
                         <button onClick={() => blockUser(user.pk)} className="p-2 bg-white border border-slate-200 rounded-lg shadow-sm hover:text-red-600 hover:border-red-400" title="Blockieren"><Ban size={20} /></button>

                         <button onClick={() => toggleHideUser(user.pk, user.status)} className="p-2 bg-white border border-slate-200 rounded-lg shadow-sm hover:text-slate-600">{isHidden ? <Users size={20} /> : <EyeOff size={20} />}</button>
                      </div>
                    </td>
                    <td className="p-6 align-top">
                      {isChanged && user.change_details && <div className="mb-2 text-xs font-bold text-yellow-800 bg-yellow-200 p-1.5 rounded inline-block">Änderung: {user.change_details}</div>}
                      <div className="text-slate-700 italic whitespace-pre-wrap leading-relaxed">{user.bio}</div>
                      {user.email && <div className="mt-3 flex items-center gap-2 text-purple-700 font-bold bg-purple-50 px-3 py-1.5 rounded w-fit text-sm"><Mail size={16} /> {user.email}</div>}
                    </td>
                    <td className="p-6 align-top">
                        <div className="font-bold text-blue-600 text-lg">{user.followers_count?.toLocaleString()}</div>
                        <div className="text-slate-400 text-sm mt-1">Followers</div>
                    </td>
                    <td className="p-6 align-top text-sm text-slate-600">
                        <div>Gefunden: {formatDate(user.found_date)}</div>
                        <div className="text-xs opacity-70 mt-1">Check: {formatDate(user.last_scraped_date)}</div>
                        <div className="text-xs text-slate-400 mt-2">Source: {user.source_account}</div>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </main>
    </div>
  );
}
