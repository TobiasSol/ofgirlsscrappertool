import React, { useState, useEffect, useMemo } from 'react';
import { Search, RefreshCw, ExternalLink, Trash2, Mail, Instagram, EyeOff, Eye, Globe } from 'lucide-react';

export default function App() {
  const [users, setUsers] = useState([]);
  const [filterText, setFilterText] = useState('');
  const [stats, setStats] = useState({ total: 0, withEmail: 0, new: 0 });
  const [loading, setLoading] = useState(true);
  const [viewMode, setViewMode] = useState('active'); // 'active' oder 'hidden'

  // Lade Einstellungen (Sprache, Hidden-Status) aus dem LocalStorage
  const getLocalPrefs = () => {
    const saved = localStorage.getItem('instaMonitor_prefs');
    return saved ? JSON.parse(saved) : {};
  };

  const [userPrefs, setUserPrefs] = useState(getLocalPrefs());

  // Speichert Preferences bei Änderung
  const updatePref = (id, key, value) => {
    const newPrefs = {
      ...userPrefs,
      [id]: { ...userPrefs[id], [key]: value }
    };
    setUserPrefs(newPrefs);
    localStorage.setItem('instaMonitor_prefs', JSON.stringify(newPrefs));
  };

  const loadData = async () => {
    try {
      setLoading(true);
      const response = await fetch('/src/data/users.json?' + new Date().getTime());
      const data = await response.json();
      setUsers(data || []);
    } catch (error) {
      console.error('Fehler beim Laden der Daten:', error);
      setUsers([]);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadData();
  }, []);

  useEffect(() => {
    if (users) {
      // Berechne Stats nur für NICHT versteckte User
      const activeUsers = users.filter(u => !userPrefs[u.id]?.hidden);
      setStats({
        total: activeUsers.length,
        withEmail: activeUsers.filter(u => u.email && u.email.length > 0).length,
        new: activeUsers.filter(u => u.status === 'new').length
      });
    }
  }, [users, userPrefs]);

  const filteredUsers = useMemo(() => {
    let list = users;

    // 1. Filter nach ViewMode (Active vs Hidden)
    if (viewMode === 'active') {
      list = list.filter(u => !userPrefs[u.id]?.hidden);
    } else {
      list = list.filter(u => userPrefs[u.id]?.hidden);
    }

    // 2. Filter nach Suchtext
    return list.filter(user => 
      ((user.username||'')+(user.bio||'')+(user.fullName||'')).toLowerCase().includes(filterText.toLowerCase())
    );
  }, [users, filterText, viewMode, userPrefs]);

  // Handler
  const toggleHidden = (id) => {
    const isHidden = !!userPrefs[id]?.hidden;
    updatePref(id, 'hidden', !isHidden);
  };

  const setLanguage = (id, lang) => {
    updatePref(id, 'lang', lang);
  };

  // Löschen entfernt es komplett aus der Ansicht (aber nicht aus JSON/DB, erst beim nächsten Python Scan theoretisch wieder da, wenn DB nicht bereinigt)
  const handleDelete = (id) => {
    if (window.confirm('Temporär aus Liste entfernen?')) setUsers(users.filter(u => u.id !== id));
  };

  return (
    <div className="min-h-screen bg-slate-50 text-slate-800 font-sans p-6">
      <nav className="mb-8 flex justify-between items-center bg-white p-4 rounded-xl shadow-sm">
        <div className="flex items-center gap-2">
            <Instagram className="text-purple-600" />
            <h1 className="text-xl font-bold">InstaMonitor Dashboard</h1>
        </div>
        <div className="flex gap-3">
          <div className="flex bg-slate-100 p-1 rounded-lg">
            <button 
              onClick={() => setViewMode('active')}
              className={`px-3 py-1.5 rounded-md text-sm font-medium transition-all ${viewMode === 'active' ? 'bg-white shadow text-purple-600' : 'text-slate-500 hover:text-slate-700'}`}
            >
              Aktive Leads
            </button>
            <button 
              onClick={() => setViewMode('hidden')}
              className={`px-3 py-1.5 rounded-md text-sm font-medium transition-all flex items-center gap-1 ${viewMode === 'hidden' ? 'bg-white shadow text-purple-600' : 'text-slate-500 hover:text-slate-700'}`}
            >
              <EyeOff size={14}/> Versteckt
            </button>
          </div>
          <button onClick={loadData} className="flex gap-2 items-center bg-slate-100 px-3 py-2 rounded-lg hover:bg-slate-200 text-sm">
              <RefreshCw size={16} /> Reload
          </button>
        </div>
      </nav>

      {/* Stats nur im Active Mode anzeigen */}
      {viewMode === 'active' && (
        <div className="grid grid-cols-1 md:grid-cols-3 gap-6 mb-6">
          <div className="bg-white p-6 rounded-xl shadow-sm border border-slate-200">
              <div className="text-slate-500 text-sm">Leads</div>
              <div className="text-2xl font-bold">{stats.total}</div>
          </div>
          <div className="bg-white p-6 rounded-xl shadow-sm border border-slate-200">
              <div className="text-slate-500 text-sm">Mit Email</div>
              <div className="text-2xl font-bold text-green-600">{stats.withEmail}</div>
          </div>
          <div className="bg-gradient-to-br from-purple-600 to-indigo-600 p-6 rounded-xl shadow-md text-white">
              <div className="text-indigo-100 text-sm">Neue Funde</div>
              <div className="text-2xl font-bold">{stats.new}</div>
          </div>
        </div>
      )}

      <div className="bg-white p-4 rounded-xl shadow-sm border border-slate-200 mb-6">
        <div className="relative">
            <Search className="absolute left-3 top-3 text-slate-400" size={18} />
            <input 
                className="w-full pl-10 pr-4 py-2 bg-slate-50 rounded-lg border border-slate-200 outline-none focus:border-purple-500"
                placeholder="Suche..."
                value={filterText}
                onChange={e => setFilterText(e.target.value)}
            />
        </div>
      </div>

      {loading ? (
        <div className="bg-white p-8 rounded-xl shadow-sm border border-slate-200 text-center">
          <div className="text-slate-500">Lade Daten...</div>
        </div>
      ) : (
      <div className="bg-white rounded-xl shadow-sm border border-slate-200 overflow-hidden">
        <table className="w-full text-left text-base">
            <thead className="bg-slate-50 text-slate-500 font-semibold border-b text-sm uppercase tracking-wider">
                <tr>
                  <th className="p-6 w-1/5">User</th>
                  <th className="p-6 w-2/5">Bio</th>
                  <th className="p-6 w-1/6">Sprache</th>
                  <th className="p-6">Kontakt</th>
                  <th className="p-6 text-right">Aktion</th>
                </tr>
            </thead>
            <tbody className="divide-y">
                {filteredUsers.length === 0 ? (
                  <tr><td colSpan="5" className="p-10 text-center text-slate-500 text-lg">Keine Daten gefunden</td></tr>
                ) : (
                  filteredUsers.map(user => {
                    const currentLang = userPrefs[user.id]?.lang;

                    return (
                    <tr key={user.pk} className={`hover:bg-slate-50 transition-colors ${user.status === 'new' && viewMode === 'active' ? 'bg-purple-50/30' : ''}`}>
                        <td className="p-6 align-top">
                            <div className="font-bold text-lg flex items-center gap-2">
                                {/* Username ist jetzt ein Link */}
                                <a 
                                  href={`https://instagram.com/${user.username}`} 
                                  target="_blank" 
                                  rel="noreferrer"
                                  className="text-slate-900 hover:text-purple-600 hover:underline flex items-center gap-1"
                                >
                                  {user.username}
                                  <ExternalLink size={14} className="opacity-50"/>
                                </a>
                                {user.status === 'new' && <span className="text-xs bg-purple-600 text-white px-2 py-0.5 rounded-full font-bold">NEU</span>}
                            </div>
                            <div className="text-slate-500 text-sm mt-1 font-medium">{user.fullName}</div>
                        </td>
                        
                        <td className="p-6 align-top text-slate-600 italic whitespace-pre-wrap text-base leading-relaxed">
                          {user.bio}
                        </td>

                        {/* SPRACH-WAHL */}
                        <td className="p-6 align-top">
                          <div className="flex flex-col gap-1">
                            <div className="flex border rounded-md overflow-hidden w-fit shadow-sm">
                              <button 
                                onClick={() => setLanguage(user.id, 'DE')}
                                className={`px-3 py-1.5 text-sm font-bold transition-colors ${currentLang === 'DE' ? 'bg-blue-600 text-white' : 'bg-white text-slate-500 hover:bg-slate-100'}`}
                              >
                                DE
                              </button>
                              <div className="w-[1px] bg-slate-200"></div>
                              <button 
                                onClick={() => setLanguage(user.id, 'EN')}
                                className={`px-3 py-1.5 text-sm font-bold transition-colors ${currentLang === 'EN' ? 'bg-blue-600 text-white' : 'bg-white text-slate-500 hover:bg-slate-100'}`}
                              >
                                EN
                              </button>
                            </div>
                          </div>
                        </td>

                        <td className="p-6 align-top">
                            {user.email ? (
                              <a href={`mailto:${user.email}`} className="text-purple-600 font-medium hover:underline flex items-center gap-2 mb-1 text-base">
                                <Mail size={16}/>{user.email}
                              </a>
                            ) : <span className="text-slate-300">-</span>}
                        </td>

                        <td className="p-6 align-top text-right">
                            <div className="flex justify-end gap-3">
                              {/* Hidden Button */}
                              <button 
                                onClick={() => toggleHidden(user.id)} 
                                className="p-3 bg-white border border-slate-200 rounded-lg hover:bg-slate-50 text-slate-400 hover:text-orange-600 transition-colors shadow-sm"
                                title={viewMode === 'active' ? "Verstecken" : "Wieder anzeigen"}
                              >
                                {viewMode === 'active' ? <EyeOff size={20}/> : <Eye size={20}/>}
                              </button>
                              
                              <button onClick={() => handleDelete(user.id)} className="p-3 bg-white border border-slate-200 rounded-lg hover:bg-slate-50 text-slate-400 hover:text-red-600 transition-colors shadow-sm">
                                <Trash2 size={20}/>
                              </button>
                            </div>
                        </td>
                    </tr>
                  )})
                )}
            </tbody>
        </table>
      </div>
      )}
    </div>
  );
}
