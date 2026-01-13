import React, { useState, useEffect, useMemo, useRef } from 'react';
import { 
  Search, RefreshCw, Trash2, Mail, Instagram, 
  CheckCircle, AlertCircle, Plus, Lock, EyeOff, Activity, ArrowUpDown, XCircle, Loader2, Ban, Heart, Copy, Check, GripVertical, Play, ExternalLink, Globe, UserPlus, Menu, LogOut, Download, Upload
} from 'lucide-react';

const API_URL = "/api"; 

// --- HELPER ---
const formatDate = (isoString) => {
  if (!isoString) return "-";
  try {
    const d = new Date(isoString);
    return d.toLocaleDateString('de-DE', { day: '2-digit', month: '2-digit', year: 'numeric' });
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
  const [isAuthenticated, setIsAuthenticated] = useState(() => localStorage.getItem('insta_auth') === 'true');
  const [password, setPassword] = useState("");
  const [loginError, setLoginError] = useState(false);
  const [appReady, setAppReady] = useState(false); 
  
  useEffect(() => {
      const loggedIn = localStorage.getItem('isLoggedIn') === 'true';
      if (loggedIn) setIsAuthenticated(true);
      setAppReady(true);
  }, []);
  
  const [users, setUsers] = useState([]);
  const [targets, setTargets] = useState([]);
  const [loading, setLoading] = useState(false);
  
  const [activeTab, setActiveTab] = useState('unfiltered'); 
  const [filterText, setFilterText] = useState('');
  const [newTarget, setNewTarget] = useState("");
  const [manualUsername, setManualUsername] = useState(""); 
  const [selectedUsers, setSelectedUsers] = useState([]); 
  const [dachFilter, setDachFilter] = useState('all');
  
  const [pageSize, setPageSize] = useState(20); 
  const [currentPage, setCurrentPage] = useState(1);
  const [sortConfig, setSortConfig] = useState({ key: 'foundDate', direction: 'desc' });
  const [hideEnglishInEmail, setHideEnglishInEmail] = useState(false);
  const [activeJob, setActiveJob] = useState(null);
  const [copySuccess, setCopySuccess] = useState(false);

  const [colWidths, setColWidths] = useState(() => {
      const saved = localStorage.getItem('instaMonitor_colWidths');
      return saved ? JSON.parse(saved) : { select: 40, user: 280, actions: 160, bio: 400, follower: 120, date: 100 };
  });

  const startResize = (e, key) => {
      const startX = e.clientX;
      const startWidth = colWidths[key];
      const onMouseMove = (moveE) => {
          setColWidths(prev => ({ ...prev, [key]: Math.max(50, startWidth + (moveE.clientX - startX)) }));
      };
      const onMouseUp = () => {
          document.removeEventListener('mousemove', onMouseMove);
          document.removeEventListener('mouseup', onMouseUp);
      };
      document.addEventListener('mousemove', onMouseMove);
      document.addEventListener('mouseup', onMouseUp);
  };

  useEffect(() => { localStorage.setItem('instaMonitor_colWidths', JSON.stringify(colWidths)); }, [colWidths]);

  const stats = useMemo(() => ({
    total: users.length,
    unfiltered: users.filter(u => ['new', 'active', 'changed', 'contacted', 'not_found'].includes(u.status)).length,
    favorites: users.filter(u => u.status === 'favorite').length,
    dach: users.filter(u => u.isGerman).length,
    eng: users.filter(u => u.status === 'eng').length,
    hidden: users.filter(u => u.status === 'hidden').length,
    blocked: users.filter(u => u.status === 'blocked').length,
    email: users.filter(u => u.email).length
  }), [users]);

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

  useEffect(() => { if (isAuthenticated) loadData(); }, [isAuthenticated]);

  useEffect(() => {
    let interval;
    if (activeJob && !['finished', 'error'].includes(activeJob.status)) {
      interval = setInterval(async () => {
        try {
          const res = await fetch(`${API_URL}/get-job-status?username=${encodeURIComponent(activeJob.username)}`);
          const data = await res.json();
          if (data.status) {
            setActiveJob(prev => ({ ...prev, ...data }));
            if (['finished', 'error'].includes(data.status)) loadData();
          }
        } catch (e) {}
      }, 1000);
    }
    return () => clearInterval(interval);
  }, [activeJob]);

  const processedUsers = useMemo(() => {
    let filtered = [...users];
    switch (activeTab) {
        case 'review': 
        case 'unfiltered': filtered = filtered.filter(u => ['new', 'active', 'changed', 'contacted', 'not_found'].includes(u.status)); break;
        case 'dach': filtered = filtered.filter(u => u.isGerman); break;
        case 'favorites': filtered = filtered.filter(u => u.status === 'favorite'); break;
        case 'eng': filtered = filtered.filter(u => u.status === 'eng'); break;
        case 'hidden': filtered = filtered.filter(u => u.status === 'hidden'); break;
        case 'blocked': filtered = filtered.filter(u => u.status === 'blocked'); break;
        case 'email': 
            filtered = filtered.filter(u => u.email && u.status !== 'blocked' && u.status !== 'hidden'); 
            if (hideEnglishInEmail) filtered = filtered.filter(u => u.status !== 'eng');
            break;
        case 'export': filtered = selectedUsers.length > 0 ? filtered.filter(u => selectedUsers.includes(u.pk)) : []; break;
    }
    if (activeTab === 'unfiltered') {
        if (dachFilter === 'de') filtered = filtered.filter(u => u.isGerman == true);
        else if (dachFilter === 'no_de') filtered = filtered.filter(u => u.isGerman == false && u.isGerman !== null);
        else if (dachFilter === 'unscanned') filtered = filtered.filter(u => u.isGerman === null);
    }
    if (filterText) {
        const l = filterText.toLowerCase();
        filtered = filtered.filter(u => (u.username||'').toLowerCase().includes(l) || (u.bio||'').toLowerCase().includes(l));
    }
    return filtered.sort((a, b) => {
        if (activeTab === 'unfiltered' && sortConfig.key === 'foundDate' && a.isGerman !== b.isGerman) return a.isGerman ? -1 : 1;
        let aV = a[sortConfig.key] || ""; let bV = b[sortConfig.key] || "";
        if (typeof aV === 'string') { aV = aV.toLowerCase(); bV = bV.toLowerCase(); }
        return aV < bV ? (sortConfig.direction === 'asc' ? -1 : 1) : (sortConfig.direction === 'asc' ? 1 : -1);
    });
  }, [users, activeTab, filterText, sortConfig, selectedUsers, dachFilter, hideEnglishInEmail]);

  const paginatedUsers = useMemo(() => processedUsers.slice((currentPage - 1) * pageSize, currentPage * pageSize), [processedUsers, currentPage, pageSize]);
  const totalPages = Math.ceil(processedUsers.length / pageSize);
  useEffect(() => { setCurrentPage(1); }, [activeTab, filterText, dachFilter, pageSize]);

  const toggleSelectAll = () => {
    const allOnPageSelected = paginatedUsers.every(u => selectedUsers.includes(u.pk));
    const pagePks = paginatedUsers.map(u => u.pk);
    if (allOnPageSelected) setSelectedUsers(prev => prev.filter(pk => !pagePks.includes(pk)));
    else setSelectedUsers(prev => [...new Set([...prev, ...pagePks])]);
  };

  const toggleSelectUser = (pk) => {
    if (selectedUsers.includes(pk)) setSelectedUsers(selectedUsers.filter(id => id !== pk));
    else setSelectedUsers([...selectedUsers, pk]);
  };

  const handleStatusChange = async (pk, newStatus) => {
    setUsers(prev => prev.map(u => u.pk === pk ? {...u, status: newStatus} : u));
    await fetch(`${API_URL}/lead/update-status`, { method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({ pk, status: newStatus })});
  };

  const requestSort = (key) => {
    let direction = 'asc';
    if (sortConfig.key === key && sortConfig.direction === 'asc') direction = 'desc';
    setSortConfig({ key, direction });
  };

  const ResizeHandle = ({ id }) => (
    <div className="absolute right-0 top-0 bottom-0 w-2 cursor-col-resize hover:bg-purple-400 z-10 opacity-0 hover:opacity-100" onMouseDown={(e) => startResize(e, id)}>
        <div className="w-[1px] h-full bg-purple-500 mx-auto"></div>
    </div>
  );

  const handleAddTarget = async () => {
    if (!newTarget) return;
    setActiveJob({ username: newTarget, status: 'running', message: 'Startet...' });
    await fetch(`${API_URL}/add-target`, { method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({ username: newTarget })});
    setNewTarget("");
  };

  const handleManualAdd = async () => {
    if (!manualUsername) return;
    setLoading(true); 
    await fetch(`${API_URL}/add-lead`, { method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({ username: manualUsername })});
    setManualUsername("");
    loadData();
  };

  const handleDachScan = async () => {
    const usersToScan = selectedUsers.length > 0 ? users.filter(u => selectedUsers.includes(u.pk)) : processedUsers;
    if (usersToScan.length === 0) return;
    const usernames = usersToScan.map(u => u.username);
    setLoading(true);
    const res = await fetch(`${API_URL}/analyze-german`, { method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({ usernames })});
    const data = await res.json();
    if (data.job_id) setActiveJob({ username: data.job_id, status: 'running', message: 'Scan läuft...' });
    setLoading(false);
  };

  const handleDeleteSelected = async () => {
    if (selectedUsers.length === 0 || !window.confirm('Löschen?')) return;
    await fetch(`${API_URL}/delete-users`, { method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({ pks: selectedUsers })});
    setSelectedUsers([]);
    loadData();
  };

  if (!isAuthenticated) return (
    <div className="min-h-screen bg-slate-900 flex items-center justify-center p-4">
      <div className="bg-white p-8 rounded-2xl shadow-2xl w-full max-w-md">
        <h2 className="text-2xl font-bold text-center mb-6">InstaMonitor Pro Login</h2>
        <form onSubmit={(e) => { e.preventDefault(); if(password === "Tobideno85!") { setIsAuthenticated(true); localStorage.setItem('insta_auth', 'true'); loadData(); } else setLoginError(true); }} className="space-y-4">
          <input type="password" title="Passwort" className="w-full px-4 py-3 border rounded-lg" placeholder="Passwort" value={password} onChange={e => setPassword(e.target.value)} autoFocus />
          {loginError && <p className="text-red-500 text-xs text-center mt-2 font-bold">Falsches Passwort</p>}
          <button className="w-full bg-purple-600 text-white font-bold py-3 rounded-lg hover:bg-purple-700 transition-all">Login</button>
        </form>
      </div>
    </div>
  );

  return (
    <div className="min-h-screen bg-slate-50 text-slate-800 font-sans">
      {!appReady && <Preloader />}
      
      {activeJob && !['finished', 'error'].includes(activeJob.status) && (
          <div className="fixed inset-0 bg-slate-900/60 backdrop-blur-sm z-[100] flex items-center justify-center p-6 text-center animate-in fade-in duration-300">
              <div className="bg-white p-8 rounded-xl shadow-2xl max-w-sm w-full space-y-4">
                  <Loader2 className="mx-auto animate-spin text-purple-600" size={40} />
                  <h2 className="text-xl font-bold">Analyse läuft...</h2>
                  <p className="text-slate-500 text-sm font-medium">{activeJob.message}</p>
              </div>
          </div>
      )}

      <nav className="bg-white border-b border-slate-200 sticky top-0 z-30 px-4 md:px-6 py-4 flex flex-col xl:flex-row items-center justify-between shadow-sm gap-4">
        <div className="flex items-center gap-2">
          <Instagram className="text-purple-600" size={28} />
          <h1 className="text-xl font-bold">InstaMonitor</h1>
        </div>
        
        <div className="flex flex-wrap justify-center gap-2">
            <TabButton active={activeTab === 'review'} onClick={() => setActiveTab('review')} label="Review" color="pink" icon={<Play size={16}/>} />
            <div className="w-[1px] bg-slate-300 mx-1"></div>
            <TabButton active={activeTab === 'unfiltered'} onClick={() => setActiveTab('unfiltered')} label="Ungefiltert" count={stats.unfiltered} color="purple"/>
            <TabButton active={activeTab === 'dach'} onClick={() => setActiveTab('dach')} label="DACH" count={stats.dach} color="orange" icon={<Globe size={16}/>}/>
            <TabButton active={activeTab === 'favorites'} onClick={() => setActiveTab('favorites')} label="Favoriten" count={stats.favorites} color="yellow"/>
            <TabButton active={activeTab === 'eng'} onClick={() => setActiveTab('eng')} label="English" count={stats.eng} color="orange" icon={<Globe size={16}/>}/>
            <TabButton active={activeTab === 'email'} onClick={() => setActiveTab('email')} label="Email" count={stats.email} color="blue"/>
            <TabButton active={activeTab === 'hidden'} onClick={() => setActiveTab('hidden')} label="Versteckt" count={stats.hidden} color="slate"/>
            <TabButton active={activeTab === 'blocked'} onClick={() => setActiveTab('blocked')} label="Blockiert" count={stats.blocked} color="red"/>
            <TabButton active={activeTab === 'export'} onClick={() => setActiveTab('export')} label="Export" color="green"/>
            <TabButton active={activeTab === 'add'} onClick={() => setActiveTab('add')} label="+" color="indigo" />
        </div>

        <div className="flex items-center gap-2">
           <div className="flex bg-slate-100 rounded-lg p-1">
             <input type="text" placeholder="Ziel..." className="bg-transparent px-3 py-1 outline-none text-sm w-32" value={newTarget} onChange={e => setNewTarget(e.target.value)} />
             <button onClick={handleAddTarget} className="bg-black text-white p-1.5 rounded-md hover:bg-slate-800"><Plus size={16} /></button>
           </div>
           <button onClick={loadData} className="p-2 hover:bg-slate-100 rounded-full transition-colors"><RefreshCw size={18} /></button>
           <button onClick={() => { setIsAuthenticated(false); localStorage.removeItem('insta_auth'); }} className="p-2 text-red-600 hover:bg-red-50 rounded-full transition-colors"><LogOut size={18}/></button>
        </div>
      </nav>

      <main className="w-full px-4 md:px-8 py-6 space-y-6">
        {activeTab === 'add' ? (
            <div className="bg-white p-8 rounded-xl border border-slate-200 text-center space-y-6 animate-in fade-in zoom-in-95">
                <h2 className="text-2xl font-bold">User manuell hinzufügen</h2>
                <div className="flex max-w-md mx-auto gap-2">
                    <input type="text" className="flex-1 p-2 border rounded-lg" placeholder="Username" value={manualUsername} onChange={e => setManualUsername(e.target.value)} />
                    <button onClick={handleManualAdd} className="bg-indigo-600 text-white px-6 py-2 rounded-lg font-bold hover:bg-indigo-700">Add</button>
                </div>
            </div>
        ) : activeTab === 'export' ? (
            <div className="bg-white p-8 rounded-xl border border-slate-200 space-y-8 animate-in fade-in zoom-in-95">
                <h2 className="text-2xl font-bold">Export / Backup</h2>
                <div className="grid md:grid-cols-2 gap-8">
                    <div className="space-y-4">
                        <h3 className="font-bold text-slate-600">Namen kopieren</h3>
                        <textarea readOnly className="w-full h-40 p-4 bg-slate-50 border rounded-lg font-mono text-sm" value={processedUsers.map(u => u.username).join('\n')} />
                        <button onClick={() => { navigator.clipboard.writeText(processedUsers.map(u => u.username).join('\n')); setCopySuccess(true); setTimeout(() => setCopySuccess(false), 2000); }} className="w-full bg-slate-800 text-white py-2 rounded-lg font-bold">{copySuccess ? 'Kopiert!' : 'Kopieren'}</button>
                    </div>
                    <div className="space-y-4">
                        <h3 className="font-bold text-slate-600">Datenbank Backup</h3>
                        <button onClick={() => window.location.href = `${API_URL}/export`} className="w-full bg-blue-600 text-white py-3 rounded-lg font-bold flex items-center justify-center gap-2"><Download size={18}/> Download JSON</button>
                        <label className="w-full border-2 border-dashed p-8 rounded-lg flex flex-col items-center gap-2 cursor-pointer hover:bg-slate-50 transition-all">
                            <Upload size={24}/> <span>JSON wiederherstellen</span>
                            <input type="file" accept=".json" className="hidden" onChange={async (e) => { const f = e.target.files[0]; if(!f) return; const fd = new FormData(); fd.append('file', f); await fetch(`${API_URL}/import`, {method: 'POST', body: fd}); loadData(); }} />
                        </label>
                    </div>
                </div>
            </div>
        ) : activeTab === 'review' ? (
            <div className="flex flex-col items-center justify-center min-h-[50vh] bg-white rounded-xl p-8 border animate-in fade-in">
                {processedUsers[0] ? (
                    <div className="text-center space-y-6 max-w-sm">
                        <div className="w-24 h-24 rounded-full bg-slate-100 mx-auto flex items-center justify-center text-3xl font-bold">{processedUsers[0].username[0].toUpperCase()}</div>
                        <h2 className="text-3xl font-bold">{processedUsers[0].username}</h2>
                        <div className="flex justify-center gap-4">
                            <button onClick={() => handleStatusChange(processedUsers[0].pk, 'favorite')} className="bg-yellow-100 text-yellow-600 p-4 rounded-2xl hover:bg-yellow-200 transition-all"><Heart size={32}/></button>
                            <button onClick={() => handleStatusChange(processedUsers[0].pk, 'blocked')} className="bg-red-100 text-red-600 p-4 rounded-2xl hover:bg-red-200 transition-all"><Ban size={32}/></button>
                        </div>
                        <p className="text-slate-600 italic whitespace-pre-wrap">{processedUsers[0].bio}</p>
                    </div>
                ) : <p className="font-bold text-slate-400 text-xl">Keine User im Review 🎉</p>}
            </div>
        ) : (
            <>
            <div className="sticky top-[130px] xl:top-[73px] z-20 flex flex-col md:flex-row justify-between items-center bg-white/90 backdrop-blur-md p-3 rounded-xl shadow-sm border border-slate-200 gap-3 mb-6 transition-all">
                <div className="flex flex-wrap items-center gap-3 w-full md:w-auto">
                    <div className="relative w-full sm:w-72">
                        <Search size={18} className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" />
                        <input type="text" placeholder="Suchen..." className="w-full pl-10 pr-4 py-2 bg-slate-50 border rounded-lg outline-none focus:border-purple-500 transition-all" value={filterText} onChange={(e) => setFilterText(e.target.value)} />
                    </div>
                    <button onClick={handleDachScan} className="bg-orange-50 text-orange-600 border border-orange-200 px-4 py-2 rounded-lg font-bold flex items-center gap-2 hover:bg-orange-100 transition-all"><Globe size={16}/> {selectedUsers.length > 0 ? `${selectedUsers.length} Scannen` : "Alle Scannen"}</button>
                    <div className="flex bg-slate-100 p-1 rounded-lg gap-1 border">
                        {['all', 'de', 'no_de', 'unscanned'].map(f => <button key={f} onClick={() => setDachFilter(f)} className={`px-3 py-1 rounded-md text-[10px] font-black tracking-tighter ${dachFilter === f ? 'bg-white text-purple-600 shadow-sm' : 'text-slate-500'}`}>{f === 'all' ? 'ALLE' : f === 'de' ? 'DE 🇩🇪' : f === 'no_de' ? 'NO DE ✘' : 'SCAN ⏳'}</button>)}
                    </div>
                </div>
                <div className="flex items-center gap-3 w-full md:w-auto justify-between">
                    <div className="flex bg-slate-50 p-1 rounded-lg border">
                        <span className="text-[10px] font-bold text-slate-400 px-2 flex items-center">SHOW:</span>
                        {[10, 20, 50, 100].map(s => <button key={s} onClick={() => setPageSize(s)} className={`px-2 py-1 rounded-md text-xs font-bold ${pageSize === s ? 'bg-white text-purple-600 shadow-sm' : 'text-slate-400'}`}>{s}</button>)}
                    </div>
                    {selectedUsers.length > 0 && (
                        <div className="flex gap-1 animate-in zoom-in-95">
                            <button onClick={() => setSelectedUsers(processedUsers.map(u => u.pk))} className="text-[10px] bg-white text-slate-700 px-2 py-1 rounded border border-slate-300 font-bold hover:bg-slate-50">Alle ({processedUsers.length})</button>
                            <button onClick={handleDeleteSelected} className="bg-red-600 text-white p-2 rounded-lg hover:bg-red-700 shadow-lg shadow-red-100"><Trash2 size={16}/></button>
                        </div>
                    )}
                </div>
            </div>

            <div className="bg-white rounded-xl border border-slate-200 overflow-x-auto relative">
                <table className="w-full text-left table-fixed">
                    <thead className="bg-slate-50 text-slate-500 font-bold border-b text-[10px] uppercase tracking-widest">
                        <tr>
                            <th className="p-4 w-12 text-center"><input type="checkbox" checked={paginatedUsers.length > 0 && paginatedUsers.every(u => selectedUsers.includes(u.pk))} onChange={toggleSelectAll} className="w-4 h-4 accent-purple-600"/></th>
                            <th className="p-4 cursor-pointer hover:bg-slate-100 transition-colors" style={{width: colWidths.user}} onClick={() => requestSort('username')}><div className="flex items-center gap-1 text-slate-700">USER {sortConfig.key === 'username' && <ArrowUpDown size={12} className={sortConfig.direction === 'asc' ? 'rotate-180' : ''}/>}</div><ResizeHandle id="user"/></th>
                            <th className="p-4" style={{width: colWidths.actions}}>AKTIONEN <ResizeHandle id="actions"/></th>
                            <th className="p-4" style={{width: colWidths.bio}}>BIOGRAFIE <ResizeHandle id="bio"/></th>
                            <th className="p-4 cursor-pointer hover:bg-slate-100 transition-colors" style={{width: colWidths.follower}} onClick={() => requestSort('followersCount')}><div className="flex items-center gap-1 text-slate-700">FOLLOWER {sortConfig.key === 'followersCount' && <ArrowUpDown size={12} className={sortConfig.direction === 'asc' ? 'rotate-180' : ''}/>}</div><ResizeHandle id="follower"/></th>
                            <th className="p-4 cursor-pointer hover:bg-slate-100 transition-colors" style={{width: colWidths.date}} onClick={() => requestSort('foundDate')}><div className="flex items-center gap-1 text-slate-700">DATUM {sortConfig.key === 'foundDate' && <ArrowUpDown size={12} className={sortConfig.direction === 'asc' ? 'rotate-180' : ''}/>}</div><ResizeHandle id="date"/></th>
                        </tr>
                    </thead>
                    <tbody className="divide-y divide-slate-100 text-sm">
                        {paginatedUsers.map((user) => {
                            const isS = selectedUsers.includes(user.pk);
                            const isG = user.isGerman;
                            const isNG = user.isGerman === false;
                            return (
                                <tr key={user.pk} className={`group transition-all hover:bg-green-50/30 ${isS ? 'bg-purple-50/50' : ''} ${isG ? 'bg-yellow-100/40' : ''} ${isNG ? 'bg-red-50/30' : ''}`}>
                                    <td className="p-4 text-center"><input type="checkbox" checked={isS} onChange={() => toggleSelectUser(user.pk)} className="w-4 h-4 accent-purple-600 transition-all scale-110"/></td>
                                    <td className="p-4 align-top">
                                        <div className="flex items-center gap-3">
                                            <div className="w-10 h-10 rounded-lg bg-slate-100 flex items-center justify-center font-black text-slate-400 shadow-inner">{user.username[0].toUpperCase()}</div>
                                            <div className="min-w-0">
                                                <div className="flex flex-wrap items-center gap-1.5">
                                                    <a href={`https://instagram.com/${user.username}`} target="_blank" className="font-bold text-slate-900 hover:text-purple-600 transition-colors block truncate">{user.username}</a>
                                                    {isG && <span className="bg-orange-100 text-orange-700 text-[10px] px-1.5 rounded font-black border border-orange-200">DE</span>}
                                                </div>
                                                <div className="text-[10px] text-slate-400 font-medium truncate">{user.fullName}</div>
                                                <div className="text-[9px] text-slate-300 font-bold uppercase mt-1 tracking-tighter">Src: {user.sourceAccount}</div>
                                                {user.status === 'new' && <span className="inline-block mt-1 bg-purple-600 text-white text-[8px] px-1.5 rounded-full font-bold">NEU</span>}
                                                {user.germanCheckResult && (isG || isNG) && (
                                                    <div className={`text-[9px] mt-1.5 font-bold px-1.5 py-0.5 rounded border ${isG ? 'bg-orange-50 text-orange-600 border-orange-100' : 'bg-red-50 text-red-600 border-red-100'}`}>DE {isG ? 'Sofort: ' : 'Scan: '}{user.germanCheckResult}</div>
                                                )}
                                            </div>
                                        </div>
                                    </td>
                                    <td className="p-4 align-top">
                                        <div className="flex gap-1">
                                            <button onClick={() => handleStatusChange(user.pk, user.status === 'favorite' ? 'active' : 'favorite')} className={`p-2 rounded-lg border transition-all ${user.status === 'favorite' ? 'bg-yellow-400 border-yellow-500 text-white shadow-md shadow-yellow-100' : 'bg-white text-slate-300 hover:bg-yellow-50 hover:text-yellow-500'}`} title="Favorit"><Heart size={16} className={user.status === 'favorite' ? 'fill-white' : ''}/></button>
                                            <button onClick={() => handleStatusChange(user.pk, user.status === 'eng' ? 'active' : 'eng')} className={`p-2 rounded-lg border transition-all ${user.status === 'eng' ? 'bg-orange-400 border-orange-500 text-white shadow-md shadow-orange-100' : 'bg-white text-slate-300 hover:bg-orange-50 hover:text-orange-500'}`} title="English"><Globe size={16}/></button>
                                            <button onClick={() => handleStatusChange(user.pk, 'blocked')} className="p-2 bg-white border rounded-lg text-slate-300 hover:text-red-600 hover:bg-red-50 transition-all" title="Blockieren"><Ban size={16}/></button>
                                            <button onClick={() => handleStatusChange(user.pk, user.status === 'hidden' ? 'active' : 'hidden')} className="p-2 bg-white border rounded-lg text-slate-300 hover:text-slate-600 transition-all" title="Verstecken"><EyeOff size={16} className={user.status === 'hidden' ? 'text-slate-600' : 'opacity-30'}/></button>
                                        </div>
                                    </td>
                                    <td className="p-4 align-top"><div className="text-slate-600 text-xs whitespace-pre-wrap line-clamp-4 leading-relaxed">{user.bio}</div></td>
                                    <td className="p-4 align-top"><div className="font-bold text-blue-600 text-base">{user.followersCount?.toLocaleString()}</div></td>
                                    <td className="p-4 align-top text-[10px] text-slate-400 font-bold">{formatDate(user.foundDate)}</td>
                                </tr>
                            );
                        })}
                    </tbody>
                </table>
            </div>
            {totalPages > 1 && (
                <div className="flex items-center justify-center gap-4 py-10">
                    <button disabled={currentPage === 1} onClick={() => setCurrentPage(prev => prev - 1)} className="p-3 bg-white border rounded-xl shadow-sm hover:text-purple-600 disabled:opacity-30 transition-all active:scale-90"><ArrowUpDown className="rotate-90" size={20} /></button>
                    <div className="flex items-center gap-2"><span className="text-xs font-black text-slate-400 uppercase tracking-widest">Seite</span><span className="bg-white px-4 py-2 rounded-xl border-2 border-purple-100 font-black text-purple-600 text-base">{currentPage}</span><span className="text-xs font-black text-slate-400 uppercase tracking-widest">von {totalPages}</span></div>
                    <button disabled={currentPage === totalPages} onClick={() => setCurrentPage(prev => prev + 1)} className="p-3 bg-white border rounded-xl shadow-sm hover:text-purple-600 disabled:opacity-30 transition-all active:scale-90"><ArrowUpDown className="-rotate-90" size={20} /></button>
                </div>
            )}
            </>
        )}
      </main>
    </div>
  );
}
