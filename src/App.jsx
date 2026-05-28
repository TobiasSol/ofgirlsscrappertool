import React, { useState, useEffect, useMemo, useRef } from 'react';
import { 
  Search, RefreshCw, Trash2, Mail, Instagram, 
  CheckCircle, AlertCircle, Plus, Lock, EyeOff, Activity, ArrowUpDown, XCircle, Loader2, Ban, Heart, Copy, Check, GripVertical, Play, ExternalLink, Globe, UserPlus, Menu, LogOut, Download, Upload
} from 'lucide-react';

const API_URL = "/api"; 

const formatDate = (isoString) => {
  if (!isoString) return "-";
  try {
    const d = new Date(isoString);
    return d.toLocaleDateString('de-DE', { day: '2-digit', month: '2-digit', year: 'numeric' });
  } catch (e) { return isoString; }
};

const TabButton = ({ active, label, count, onClick, color = "purple", icon }) => {
    const baseClass = "px-3 py-2 rounded-lg text-sm font-bold transition-all flex items-center gap-2 whitespace-nowrap";
    // Aktiver Tab IMMER kraeftig gruen, damit man auf den ersten Blick sieht wo man ist.
    const activeClass = active
        ? "bg-green-500 text-white border border-green-600 shadow-lg shadow-green-200 ring-2 ring-green-300"
        : "text-slate-500 hover:bg-slate-50 border border-transparent";

    return (
        <button onClick={onClick} className={`${baseClass} ${activeClass}`}>
            {icon}
            {label}
            {count !== undefined && <span className={`px-1.5 py-0.5 rounded-full text-xs font-black ${active ? 'bg-white/95 text-green-700 border border-green-200' : `bg-white text-slate-600 opacity-80 border border-${color}-200`}`}>{count}</span>}
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

const IS_LOCAL = typeof window !== 'undefined' && ['localhost', '127.0.0.1', '::1'].includes(window.location.hostname);

// --- Sek -> "mm:ss" / "hh:mm:ss" ---
const formatDuration = (totalSeconds) => {
    if (totalSeconds == null || totalSeconds < 0) return "-";
    const h = Math.floor(totalSeconds / 3600);
    const m = Math.floor((totalSeconds % 3600) / 60);
    const s = totalSeconds % 60;
    if (h > 0) return `${h}h ${String(m).padStart(2,'0')}m ${String(s).padStart(2,'0')}s`;
    if (m > 0) return `${m}m ${String(s).padStart(2,'0')}s`;
    return `${s}s`;
};

// Persistenter Scan-Banner. Pollt /api/scans/active und ist von ueberall sichtbar.
// Bleibt nach Reload + Login von anderem Geraet bestehen, weil der State in der DB liegt.
const ScanBanner = ({ scan, recent, onStop }) => {
    if (!scan && !recent) return null;
    const isRecent = !scan && recent;
    const j = scan || recent;
    const percent = j.percent || 0;
    const isStopping = j.stopRequested && j.status === 'running';
    // Stall-Erkennung: kein Heartbeat seit > 90 Sek -> wahrscheinlich haengender API-Call
    const stale = (j.staleSeconds || 0) > 90;
    const reallyStuck = (j.staleSeconds || 0) > 180;  // > 3 Min = ziemlich sicher tot

    const statusColor = reallyStuck
        ? 'from-red-600 to-red-700'
        : stale
        ? 'from-amber-500 to-orange-600'
        : ({
            running: 'from-orange-500 to-pink-500',
            finished: 'from-green-500 to-emerald-500',
            error: 'from-red-500 to-rose-500',
            stopped: 'from-slate-500 to-slate-600',
            interrupted: 'from-amber-500 to-orange-500',
        }[j.status] || 'from-slate-500 to-slate-600');

    const statusLabel = reallyStuck
        ? `⚠ Scan hängt seit ${Math.floor((j.staleSeconds || 0) / 60)}min — bitte stoppen`
        : stale
        ? `⏳ Kein Lebenszeichen seit ${j.staleSeconds}s — Profil hängt evtl.`
        : ({
            running: isStopping ? 'Wird gestoppt...' : 'Scan läuft',
            finished: '✓ Scan abgeschlossen',
            error: '✗ Fehler',
            stopped: '◼ Scan gestoppt',
            interrupted: '⚠ Unterbrochen (Server-Restart)',
        }[j.status] || j.status);

    return (
        <div className={`sticky top-0 z-50 bg-gradient-to-r ${statusColor} text-white shadow-lg animate-in slide-in-from-top duration-300`}>
            <div className="w-full px-4 md:px-8 py-3">
                <div className="flex flex-col md:flex-row items-start md:items-center gap-3">
                    <div className="flex items-center gap-2 min-w-0 flex-1">
                        {j.status === 'running' && !isStopping && <Loader2 size={18} className="animate-spin flex-shrink-0"/>}
                        <div className="min-w-0">
                            <div className="font-bold text-sm truncate">{statusLabel} — {j.label || j.type}</div>
                            <div className="text-xs opacity-90 truncate">{j.message}</div>
                        </div>
                    </div>

                    {j.total > 0 && (
                        <div className="flex items-center gap-3 text-xs flex-shrink-0">
                            <span className="font-mono bg-black/20 rounded px-2 py-1">{j.processed}/{j.total}</span>
                            <span className="font-mono bg-black/20 rounded px-2 py-1">{percent.toFixed(1)}%</span>
                        </div>
                    )}
                    {j.type === 'target' && j.found != null && (
                        <span className="font-mono bg-black/20 rounded px-2 py-1 text-xs flex-shrink-0">{j.found} neu</span>
                    )}

                    <div className="flex items-center gap-2 text-xs flex-shrink-0">
                        <div className="bg-black/20 rounded px-2 py-1">⏱ {formatDuration(j.elapsedSeconds)}</div>
                        {j.etaSeconds != null && <div className="bg-black/20 rounded px-2 py-1">noch {formatDuration(j.etaSeconds)}</div>}
                    </div>

                    {j.status === 'running' && !isRecent && (
                        <button
                            onClick={() => onStop(j.id)}
                            disabled={isStopping}
                            className="bg-white text-red-600 hover:bg-red-50 disabled:opacity-50 disabled:cursor-not-allowed font-bold px-4 py-1.5 rounded-lg text-xs flex items-center gap-1 shadow-md flex-shrink-0"
                        >
                            <XCircle size={14}/> {isStopping ? 'Stoppe...' : 'Stop'}
                        </button>
                    )}
                </div>

                {j.total > 0 && (
                    <div className="mt-2 h-1.5 bg-black/30 rounded-full overflow-hidden">
                        <div
                            className="h-full bg-white/90 transition-all duration-500 ease-out"
                            style={{width: `${Math.min(100, percent)}%`}}
                        />
                    </div>
                )}
            </div>
        </div>
    );
};

export default function App() {
  const [isAuthenticated, setIsAuthenticated] = useState(() => IS_LOCAL || localStorage.getItem('insta_auth') === 'true');
  const [password, setPassword] = useState("");
  const [loginError, setLoginError] = useState(false);
  const [appReady, setAppReady] = useState(false); 
  
  useEffect(() => {
      if (IS_LOCAL) { setIsAuthenticated(true); setAppReady(true); return; }
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
  const [exportFilter, setExportFilter] = useState('all'); // all | exported | not_exported (greift im Favoriten-Tab)
  const [scanFilter, setScanFilter] = useState('all'); // all | scanned | unscanned (greift in Favoriten + Ungefiltert)
  
  const [pageSize, setPageSize] = useState(20); 
  const [currentPage, setCurrentPage] = useState(1);
  const [sortConfig, setSortConfig] = useState({ key: 'foundDate', direction: 'desc' });
  const [hideEnglishInEmail, setHideEnglishInEmail] = useState(false);
  const [activeScan, setActiveScan] = useState(null);     // aktueller Job aus DB (Polling /api/scans/active)
  const [recentScan, setRecentScan] = useState(null);     // gerade beendet, kurz weiter anzeigen
  const [copySuccess, setCopySuccess] = useState(false);
  const [exportHistory, setExportHistory] = useState([]); // Liste aller Export-Vorgaenge aus /api/exports
  const [copiedExportId, setCopiedExportId] = useState(null); // fuer "Kopiert!"-Feedback pro Export-Eintrag

  const [colWidths, setColWidths] = useState(() => {
      const saved = localStorage.getItem('instaMonitor_colWidths');
      const defaults = { select: 40, user: 280, email: 220, actions: 160, bio: 400, follower: 120, date: 100, lastScan: 130 };
      if (!saved) return defaults;
      try {
          const parsed = JSON.parse(saved);
          return { ...defaults, ...parsed };
      } catch {
          return defaults;
      }
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

  const stats = useMemo(() => {
    const live = users.filter(u => !u.notFoundDate); // ALLE Counts (ausser offline) ignorieren tote Profile
    return {
      total: users.length,
      offline: users.filter(u => !!u.notFoundDate).length,
      unfiltered: live.filter(u => ['new', 'active', 'changed', 'contacted', 'not_found'].includes(u.status)).length,
      favorites: live.filter(u => u.status === 'favorite').length,
      dach: live.filter(u => u.isGerman).length,
      eng: live.filter(u => u.status === 'eng').length,
      hidden: live.filter(u => u.status === 'hidden').length,
      blocked: live.filter(u => u.status === 'blocked').length,
      email: live.filter(u => u.email).length,
    };
  }, [users]);

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

  const loadExports = async () => {
    try {
      const res = await fetch(`${API_URL}/exports`);
      if (!res.ok) return;
      const data = await res.json();
      setExportHistory(data.exports || []);
    } catch (e) { /* ignorieren - naechster Tab-Wechsel laedt erneut */ }
  };

  useEffect(() => { if (isAuthenticated) { loadData(); loadExports(); } }, [isAuthenticated]);
  useEffect(() => { if (activeTab === 'export') loadExports(); }, [activeTab]);

  // GLOBALES SCAN-POLLING. Laeuft ununterbrochen wenn eingeloggt.
  // Holt den aktiven Scan-Status aus der DB - funktioniert daher
  // auch nach Reload, von anderen Geraeten und nach Render-Restarts.
  useEffect(() => {
    if (!isAuthenticated) return;
    let cancelled = false;
    let lastStatus = null;

    const tick = async () => {
      try {
        const res = await fetch(`${API_URL}/scans/active`);
        if (!res.ok) return;
        const data = await res.json();
        if (cancelled) return;

        if (data.active) {
          setActiveScan(data.job);
          setRecentScan(null);
          lastStatus = 'running';
        } else {
          setActiveScan(null);
          setRecentScan(data.recent || null);
          // Wenn gerade von "running" zu fertig gewechselt -> Lead-Liste neu laden
          if (lastStatus === 'running' && data.recent) {
            loadData();
            lastStatus = data.recent.status;
          }
        }
      } catch (e) { /* Netzwerkfehler ignorieren, naechster Tick */ }
    };

    tick();
    const interval = setInterval(tick, 2000);
    return () => { cancelled = true; clearInterval(interval); };
  }, [isAuthenticated]);

  const stopActiveScan = async (jobId) => {
    try {
      await fetch(`${API_URL}/scans/${jobId}/stop`, { method: 'POST' });
    } catch (e) { /* nichts - der naechste Tick zeigt das Ergebnis */ }
  };

  const handleAddTarget = async () => {
    if (!newTarget) return;
    const res = await fetch(`${API_URL}/add-target`, {
      method: 'POST', headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({ username: newTarget })
    });
    if (res.status === 409) {
      alert('Es laeuft bereits ein Scan. Bitte erst stoppen oder warten.');
      return;
    }
    setNewTarget("");
    // ScanBanner zeigt den Job automatisch beim naechsten Tick.
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
    const res = await fetch(`${API_URL}/analyze-german`, {
      method: 'POST', headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({ usernames })
    });
    setLoading(false);
    if (res.status === 409) {
      alert('Es laeuft bereits ein Scan. Bitte erst stoppen oder warten.');
      return;
    }
    // ScanBanner zeigt den Job automatisch beim naechsten Tick (~ 2 Sek).
  };

  const handleDeleteSelected = async () => {
    if (selectedUsers.length === 0 || !window.confirm('Löschen?')) return;
    await fetch(`${API_URL}/delete-users`, { method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({ pks: selectedUsers })});
    setSelectedUsers([]);
    loadData();
  };

  const handleStatusChange = async (pk, newStatus) => {
    setUsers(prev => prev.map(u => u.pk === pk ? {...u, status: newStatus} : u));
    await fetch(`${API_URL}/lead/update-status`, { method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({ pk, status: newStatus })});
  };

  const handleExportEmails = async () => {
    const emailRegex = /[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}/g;
    const allEmails = [];
    const exportedPks = [];

    processedUsers.forEach(u => {
      // Suche im E-Mail-Feld
      const foundInEmail = (u.email || "").match(emailRegex);
      if (foundInEmail) {
        allEmails.push(...foundInEmail);
        exportedPks.push(u.pk);
        return;
      }
      // Falls dort nichts war, suche sicherheitshalber auch in der Bio
      const foundInBio = (u.bio || "").match(emailRegex);
      if (foundInBio) {
        allEmails.push(...foundInBio);
        exportedPks.push(u.pk);
      }
    });

    // Dubletten entfernen und säubern
    const uniqueEmails = [...new Set(allEmails.map(e => e.toLowerCase().trim()))].join('\n');

    if (!uniqueEmails) {
        alert("Keine gültigen E-Mail-Adressen zum Exportieren gefunden.");
        return;
    }

    const blob = new Blob([uniqueEmails], { type: 'text/plain' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `nur_emails_${new Date().toISOString().split('T')[0]}.txt`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);

    // Alle User mit exportierter Email serverseitig als 'exportiert' markieren,
    // damit man im Favoriten-Tab nach 'schon exportiert' / 'nicht exportiert' filtern kann.
    if (exportedPks.length > 0) {
      try {
        // 'emails'-Export in der Historie ablegen, damit man ihn spaeter
        // wieder runterladen / kopieren kann.
        const res = await fetch(`${API_URL}/exports`, {
          method: 'POST',
          headers: {'Content-Type': 'application/json'},
          body: JSON.stringify({
            pks: exportedPks,
            kind: 'emails',
            label: `Email-Export ${new Date().toLocaleString('de-DE')} (${exportedPks.length} User)`,
          }),
        });
        if (res.ok) {
          const data = await res.json();
          const exportedAt = data.exportedAt || new Date().toISOString();
          setUsers(prev => prev.map(u => exportedPks.includes(u.pk) ? { ...u, lastExported: exportedAt } : u));
          loadExports();
        }
      } catch (e) { /* Fehler ignorieren - Datei ist trotzdem exportiert */ }
    }
  };

  // --- Export-Historie: Aktionen ---

  const handleCreateExport = async (kind = 'usernames') => {
    // Wenn User ausgewaehlt sind nehmen wir die, sonst die aktuelle Tab-Ansicht.
    const sourceUsers = selectedUsers.length > 0
      ? users.filter(u => selectedUsers.includes(u.pk))
      : processedUsers;
    if (sourceUsers.length === 0) {
      alert("Keine User zum Exportieren ausgewählt.");
      return;
    }
    const pks = sourceUsers.map(u => u.pk);
    const labelKind = kind === 'emails' ? 'Email-Export' : 'Namen-Export';
    const label = `${labelKind} ${new Date().toLocaleString('de-DE')} (${pks.length} User)`;
    try {
      const res = await fetch(`${API_URL}/exports`, {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({ pks, kind, label }),
      });
      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        alert(`Export fehlgeschlagen: ${err.error || res.status}`);
        return;
      }
      const data = await res.json();
      const exportedAt = data.exportedAt || new Date().toISOString();
      setUsers(prev => prev.map(u => pks.includes(u.pk) ? { ...u, lastExported: exportedAt } : u));
      setSelectedUsers([]);
      await loadExports();
      // Wechsele direkt in den Export-Tab, damit der User sieht wo seine Datei ist
      setActiveTab('export');
    } catch (e) {
      alert("Netzwerkfehler beim Export.");
    }
  };

  const _fetchExportPayload = async (exportId) => {
    const res = await fetch(`${API_URL}/exports/${exportId}`);
    if (!res.ok) return null;
    return await res.json();
  };

  const handleDownloadExport = async (exportEntry, kind) => {
    // kind: 'usernames' | 'emails' - ueberschreibt den gespeicherten Export-Typ
    // damit man auch "nur Emails" aus einem Namen-Export ziehen kann.
    const payload = await _fetchExportPayload(exportEntry.id);
    if (!payload) { alert("Export konnte nicht geladen werden."); return; }
    const list = (kind === 'emails') ? (payload.emails || []) : (payload.usernames || []);
    if (list.length === 0) {
      alert(kind === 'emails' ? "Dieser Export enthält keine Emails." : "Dieser Export enthält keine Namen.");
      return;
    }
    const text = list.join('\n');
    const blob = new Blob([text], { type: 'text/plain' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    const stamp = (exportEntry.createdAt || new Date().toISOString()).replace(/[:.]/g, '-').split('T').join('_').slice(0, 19);
    a.href = url;
    a.download = `${kind === 'emails' ? 'emails' : 'usernames'}_${stamp}.txt`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
  };

  const handleCopyExport = async (exportEntry, kind) => {
    const payload = await _fetchExportPayload(exportEntry.id);
    if (!payload) { alert("Export konnte nicht geladen werden."); return; }
    const list = (kind === 'emails') ? (payload.emails || []) : (payload.usernames || []);
    if (list.length === 0) {
      alert(kind === 'emails' ? "Dieser Export enthält keine Emails." : "Dieser Export enthält keine Namen.");
      return;
    }
    try {
      await navigator.clipboard.writeText(list.join('\n'));
      setCopiedExportId(`${exportEntry.id}-${kind}`);
      setTimeout(() => setCopiedExportId(null), 1500);
    } catch (e) {
      alert("Kopieren fehlgeschlagen.");
    }
  };

  const handleDeleteExport = async (exportId) => {
    if (!window.confirm("Diesen Export-Eintrag wirklich löschen? Die User selbst bleiben erhalten.")) return;
    try {
      const res = await fetch(`${API_URL}/exports/${exportId}`, { method: 'DELETE' });
      if (res.ok) loadExports();
    } catch (e) { /* still */ }
  };

  const requestSort = (key) => {
    let direction = 'asc';
    if (sortConfig.key === key && sortConfig.direction === 'asc') direction = 'desc';
    setSortConfig({ key, direction });
  };

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
        case 'offline': filtered = filtered.filter(u => !!u.notFoundDate); break;
        case 'email':
            filtered = filtered.filter(u => u.email && u.status !== 'blocked' && u.status !== 'hidden');
            break;
        case 'export': filtered = selectedUsers.length > 0 ? filtered.filter(u => selectedUsers.includes(u.pk)) : []; break;
    }
    // Globale Regel: Offline-User (Profil existiert nicht mehr) NUR im 'offline'-Tab zeigen.
    // In allen anderen Tabs werden sie ausgeblendet, damit man nicht mehr mit toten Profilen arbeitet.
    if (activeTab !== 'offline' && activeTab !== 'export') {
        filtered = filtered.filter(u => !u.notFoundDate);
    }
    if (activeTab === 'unfiltered' || activeTab === 'favorites') {
        if (dachFilter === 'de') filtered = filtered.filter(u => u.isGerman === true);
        else if (dachFilter === 'no_de') filtered = filtered.filter(u => u.isGerman === false);
        else if (dachFilter === 'unscanned') filtered = filtered.filter(u => u.isGerman === null);
        // 'NUR GESCANNT' = nur User mit echtem Datum (lastScrapedDate ODER notFoundDate).
        // User die nur 'germanCheckResult' aus alten Scans (ohne Datum) haben, gelten
        // als ungescannt - sonst kann man sie nie nachscannen / sehen wann sie dran waren.
        if (scanFilter === 'scanned') filtered = filtered.filter(u => u.lastScrapedDate || u.notFoundDate);
        else if (scanFilter === 'unscanned') filtered = filtered.filter(u => !u.lastScrapedDate && !u.notFoundDate);
    }
    if (activeTab === 'favorites') {
        if (exportFilter === 'exported') filtered = filtered.filter(u => !!u.lastExported);
        else if (exportFilter === 'not_exported') filtered = filtered.filter(u => !u.lastExported);
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
  }, [users, activeTab, filterText, sortConfig, selectedUsers, dachFilter, exportFilter, scanFilter]);

  const paginatedUsers = useMemo(() => processedUsers.slice((currentPage - 1) * pageSize, currentPage * pageSize), [processedUsers, currentPage, pageSize]);
  const totalPages = Math.ceil(processedUsers.length / pageSize);
  useEffect(() => { setCurrentPage(1); }, [activeTab, filterText, dachFilter, exportFilter, scanFilter, pageSize]);

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

  const ResizeHandle = ({ id }) => (
    <div className="absolute right-0 top-0 bottom-0 w-2 cursor-col-resize hover:bg-purple-400 z-10 opacity-0 hover:opacity-100" onMouseDown={(e) => startResize(e, id)}>
        <div className="w-[1px] h-full bg-purple-500 mx-auto"></div>
    </div>
  );

  if (!isAuthenticated) return (
    <div className="min-h-screen bg-slate-900 flex items-center justify-center p-4">
      <div className="bg-white p-8 rounded-2xl shadow-2xl w-full max-w-md">
        <h2 className="text-2xl font-bold text-center mb-6">InstaMonitor Pro Login</h2>
        <form onSubmit={async (e) => {
          e.preventDefault();
          setLoginError(false);
          try {
            const res = await fetch(`${API_URL}/login`, {
              method: 'POST',
              headers: { 'Content-Type': 'application/json' },
              body: JSON.stringify({ password })
            });
            if (res.ok) {
              setIsAuthenticated(true);
              localStorage.setItem('insta_auth', 'true');
              loadData();
            } else {
              setLoginError(true);
            }
          } catch (err) {
            setLoginError(true);
          }
        }} className="space-y-4">
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

      <ScanBanner scan={activeScan} recent={recentScan} onStop={stopActiveScan} />

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
            <TabButton active={activeTab === 'offline'} onClick={() => setActiveTab('offline')} label="Offline" count={stats.offline} color="red" icon={<XCircle size={16}/>}/>
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
            <div className="space-y-6 animate-in fade-in zoom-in-95">
                {/* === EXPORT-HISTORIE === */}
                <div className="bg-white p-6 md:p-8 rounded-xl border border-slate-200 space-y-5">
                    <div className="flex items-center justify-between flex-wrap gap-3">
                        <div>
                            <h2 className="text-2xl font-bold flex items-center gap-2"><Download size={22} className="text-green-600"/> Export-Historie</h2>
                            <p className="text-sm text-slate-500 mt-1">Alle Export-Vorgänge mit Datum & Uhrzeit. Du kannst sie jederzeit erneut runterladen oder die Namen/Emails kopieren.</p>
                        </div>
                        <button onClick={loadExports} className="text-xs px-3 py-1.5 border border-slate-200 rounded-lg hover:bg-slate-50 flex items-center gap-2"><RefreshCw size={12}/> Aktualisieren</button>
                    </div>

                    {exportHistory.length === 0 ? (
                        <div className="text-center py-12 border-2 border-dashed border-slate-200 rounded-xl">
                            <Download size={32} className="mx-auto text-slate-300 mb-3"/>
                            <p className="text-slate-500 font-bold">Noch keine Exports vorhanden</p>
                            <p className="text-xs text-slate-400 mt-2">Wähle in der Liste User aus und klicke auf "exportieren" oder nutze "Emails (.txt)" im Email-Tab.</p>
                        </div>
                    ) : (
                        <div className="space-y-3">
                            {exportHistory.map(ex => {
                                const created = ex.createdAt ? new Date(ex.createdAt) : null;
                                const dateStr = created ? created.toLocaleDateString('de-DE', { day: '2-digit', month: '2-digit', year: 'numeric' }) : '?';
                                const timeStr = created ? created.toLocaleTimeString('de-DE', { hour: '2-digit', minute: '2-digit' }) : '';
                                const isEmail = ex.kind === 'emails';
                                return (
                                    <div key={ex.id} className="border border-slate-200 rounded-xl p-4 hover:border-green-300 hover:bg-green-50/30 transition-all">
                                        <div className="flex items-start justify-between gap-3 flex-wrap">
                                            <div className="min-w-0 flex-1">
                                                <div className="flex items-center gap-2 flex-wrap">
                                                    <span className={`text-[9px] font-black px-2 py-0.5 rounded uppercase tracking-widest ${isEmail ? 'bg-blue-100 text-blue-700 border border-blue-200' : 'bg-green-100 text-green-700 border border-green-200'}`}>
                                                        {isEmail ? 'EMAILS' : 'NAMEN'}
                                                    </span>
                                                    <span className="font-bold text-slate-800 truncate">{ex.label}</span>
                                                </div>
                                                <div className="flex items-center gap-3 mt-1.5 text-xs text-slate-500">
                                                    <span className="font-mono bg-slate-100 px-2 py-0.5 rounded">{ex.count} User</span>
                                                    <span className="font-mono">{dateStr} {timeStr} Uhr</span>
                                                </div>
                                                {ex.preview && ex.preview.length > 0 && (
                                                    <div className="mt-2 text-[11px] text-slate-400 truncate font-mono">
                                                        {ex.preview.join(', ')}{ex.count > ex.preview.length ? ` … +${ex.count - ex.preview.length}` : ''}
                                                    </div>
                                                )}
                                            </div>
                                            <div className="flex items-center gap-1.5 flex-wrap justify-end">
                                                <button
                                                    onClick={() => handleDownloadExport(ex, 'usernames')}
                                                    className="bg-slate-800 text-white px-3 py-1.5 rounded-md text-xs font-bold flex items-center gap-1 hover:bg-slate-900"
                                                    title="Namen als .txt-Datei runterladen"
                                                >
                                                    <Download size={12}/> Namen .txt
                                                </button>
                                                <button
                                                    onClick={() => handleCopyExport(ex, 'usernames')}
                                                    className="bg-white text-slate-700 border border-slate-300 px-3 py-1.5 rounded-md text-xs font-bold flex items-center gap-1 hover:bg-slate-50"
                                                    title="Namen in Zwischenablage kopieren"
                                                >
                                                    {copiedExportId === `${ex.id}-usernames` ? <><Check size={12} className="text-green-600"/> Kopiert</> : <><Copy size={12}/> Namen kopieren</>}
                                                </button>
                                                <button
                                                    onClick={() => handleDownloadExport(ex, 'emails')}
                                                    className="bg-blue-600 text-white px-3 py-1.5 rounded-md text-xs font-bold flex items-center gap-1 hover:bg-blue-700"
                                                    title="Emails als .txt-Datei runterladen"
                                                >
                                                    <Mail size={12}/> Emails .txt
                                                </button>
                                                <button
                                                    onClick={() => handleCopyExport(ex, 'emails')}
                                                    className="bg-white text-blue-700 border border-blue-200 px-3 py-1.5 rounded-md text-xs font-bold flex items-center gap-1 hover:bg-blue-50"
                                                    title="Emails in Zwischenablage kopieren"
                                                >
                                                    {copiedExportId === `${ex.id}-emails` ? <><Check size={12} className="text-green-600"/> Kopiert</> : <><Copy size={12}/> Emails kopieren</>}
                                                </button>
                                                <button
                                                    onClick={() => handleDeleteExport(ex.id)}
                                                    className="bg-white text-red-500 border border-red-100 p-1.5 rounded-md hover:bg-red-50"
                                                    title="Aus Historie löschen (User bleiben erhalten)"
                                                >
                                                    <Trash2 size={12}/>
                                                </button>
                                            </div>
                                        </div>
                                    </div>
                                );
                            })}
                        </div>
                    )}
                </div>

                {/* === SCHNELL-EXPORT (aktuelle Tab-Ansicht) === */}
                <div className="bg-white p-6 md:p-8 rounded-xl border border-slate-200 space-y-4">
                    <h3 className="font-bold text-slate-700 text-lg">Schnell-Export aktueller Ansicht</h3>
                    <p className="text-xs text-slate-500 -mt-2">Exportiert die User aus dem aktuell aktiven Tab (oder, wenn welche ausgewählt sind, nur die ausgewählten). Wird in der Historie oben gespeichert.</p>
                    <div className="flex gap-3 flex-wrap">
                        <button onClick={() => handleCreateExport('usernames')} className="bg-green-600 text-white px-4 py-2 rounded-lg font-bold flex items-center gap-2 hover:bg-green-700"><Download size={16}/> Namen exportieren</button>
                        <button onClick={() => handleCreateExport('emails')} className="bg-blue-600 text-white px-4 py-2 rounded-lg font-bold flex items-center gap-2 hover:bg-blue-700"><Mail size={16}/> Emails exportieren</button>
                        <button onClick={() => { navigator.clipboard.writeText(processedUsers.map(u => u.username).join('\n')); setCopySuccess(true); setTimeout(() => setCopySuccess(false), 2000); }} className="bg-slate-800 text-white px-4 py-2 rounded-lg font-bold flex items-center gap-2"><Copy size={16}/> {copySuccess ? 'Kopiert!' : 'Namen schnell kopieren'}</button>
                    </div>
                </div>

                {/* === DATENBANK BACKUP === */}
                <div className="bg-white p-6 md:p-8 rounded-xl border border-slate-200 space-y-4">
                    <h3 className="font-bold text-slate-700 text-lg">Datenbank Backup</h3>
                    <div className="grid md:grid-cols-2 gap-4">
                        <button onClick={() => window.location.href = `${API_URL}/export`} className="w-full bg-blue-600 text-white py-3 rounded-lg font-bold flex items-center justify-center gap-2"><Download size={18}/> Download JSON</button>
                        <label className="w-full border-2 border-dashed p-6 rounded-xl flex flex-col items-center gap-2 cursor-pointer hover:bg-slate-50 transition-all">
                            <Upload size={24}/> <span className="font-bold text-sm">JSON wiederherstellen</span>
                            <input type="file" accept=".json" className="hidden" onChange={async (e) => { const f = e.target.files[0]; if(!f) return; const fd = new FormData(); fd.append('file', f); await fetch(`${API_URL}/import`, {method: 'POST', body: fd}); loadData(); }} />
                        </label>
                    </div>
                </div>
            </div>
        ) : (
            <>
            <div className="sticky top-[73px] z-20 flex flex-col md:flex-row justify-between items-center bg-white/90 backdrop-blur-md p-3 rounded-xl shadow-sm border border-slate-200 gap-3 mb-6">
                <div className="flex flex-wrap items-center justify-center md:justify-start gap-3 w-full md:w-auto">
                    <div className="relative w-full sm:w-64 md:w-72"><Search size={18} className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" /><input type="text" placeholder="Suchen..." className="w-full pl-10 pr-4 py-2 bg-slate-50 border rounded-xl outline-none focus:border-purple-500" value={filterText} onChange={(e) => setFilterText(e.target.value)} /></div>
                    <button onClick={handleDachScan} className="bg-orange-50 text-orange-600 border border-orange-200 px-4 py-2 rounded-lg font-bold flex items-center gap-2 hover:bg-orange-100 transition-all"><Globe size={16}/> {selectedUsers.length > 0 ? `${selectedUsers.length} Scannen` : "Alle Scannen"}</button>
                    {(activeTab === 'unfiltered' || activeTab === 'favorites') && (
                        <div className="flex bg-slate-100 p-1 rounded-lg gap-1 border">
                            {['all', 'de', 'no_de', 'unscanned'].map(f => <button key={f} onClick={() => setDachFilter(f)} className={`px-3 py-1 rounded-md text-xs font-bold ${dachFilter === f ? 'bg-white text-purple-600 shadow-sm' : 'text-slate-500'}`}>{f.toUpperCase()}</button>)}
                        </div>
                    )}
                    {(activeTab === 'unfiltered' || activeTab === 'favorites') && (
                        <div className="flex bg-slate-100 p-1 rounded-lg gap-1 border">
                            {[
                                {key: 'all', label: 'ALLE'},
                                {key: 'scanned', label: 'NUR GESCANNT'},
                                {key: 'unscanned', label: 'NUR UNGESCANNT'},
                            ].map(f => (
                                <button
                                    key={f.key}
                                    onClick={() => setScanFilter(f.key)}
                                    className={`px-3 py-1 rounded-md text-xs font-bold ${scanFilter === f.key ? 'bg-white text-blue-600 shadow-sm' : 'text-slate-500'}`}
                                >
                                    {f.label}
                                </button>
                            ))}
                        </div>
                    )}
                    {activeTab === 'favorites' && (
                        <div className="flex bg-slate-100 p-1 rounded-lg gap-1 border">
                            {[
                                {key: 'all', label: 'ALL'},
                                {key: 'exported', label: 'SCHON EXPORTIERT'},
                                {key: 'not_exported', label: 'NICHT EXPORTIERT'},
                            ].map(f => (
                                <button
                                    key={f.key}
                                    onClick={() => setExportFilter(f.key)}
                                    className={`px-3 py-1 rounded-md text-xs font-bold ${exportFilter === f.key ? 'bg-white text-green-600 shadow-sm' : 'text-slate-500'}`}
                                >
                                    {f.label}
                                </button>
                            ))}
                        </div>
                    )}
                </div>
                <div className="flex items-center gap-3 w-full md:w-auto justify-between">
                    <div className="text-[10px] font-black text-slate-400 bg-slate-100 px-2 py-1 rounded-full uppercase tracking-tighter">{processedUsers.length} User</div>
                    
                    {activeTab === 'email' && (
                        <button 
                            onClick={handleExportEmails}
                            className="bg-blue-600 text-white px-3 py-1.5 rounded-lg text-xs font-bold flex items-center gap-2 hover:bg-blue-700 transition-all shadow-sm"
                        >
                            <Download size={14}/> Emails (.txt)
                        </button>
                    )}

                    <div className="flex bg-slate-50 p-1 rounded-lg border">
                        {[10, 20, 50, 100].map(s => <button key={s} onClick={() => setPageSize(s)} className={`px-2 py-1 rounded-md text-xs font-bold ${pageSize === s ? 'bg-white text-purple-600 shadow-sm' : 'text-slate-400'}`}>{s}</button>)}
                    </div>
                    {selectedUsers.length > 0 && (
                        <button
                            onClick={() => handleCreateExport('usernames')}
                            className="bg-green-600 text-white px-3 py-1.5 rounded-lg text-xs font-bold flex items-center gap-2 hover:bg-green-700 transition-all shadow-lg shadow-green-100"
                            title={`${selectedUsers.length} ausgewählte User exportieren`}
                        >
                            <Download size={14}/> {selectedUsers.length} exportieren
                        </button>
                    )}
                    {selectedUsers.length > 0 && <button onClick={handleDeleteSelected} className="bg-red-600 text-white p-2 rounded-lg hover:bg-red-700 shadow-lg shadow-red-100"><Trash2 size={16}/></button>}
                </div>
            </div>

            <div className="bg-white rounded-xl border border-slate-200 overflow-x-auto relative">
                <table className="w-full text-left table-fixed">
                    <thead className="bg-slate-50 text-slate-500 font-bold border-b text-[10px] uppercase tracking-wider">
                        <tr>
                            <th className="p-4 w-12 text-center"><input type="checkbox" checked={paginatedUsers.length > 0 && paginatedUsers.every(u => selectedUsers.includes(u.pk))} onChange={toggleSelectAll} className="w-4 h-4 accent-purple-600"/></th>
                            <th className="p-4 cursor-pointer" style={{width: colWidths.user}} onClick={() => requestSort('username')}><div className="flex items-center gap-1">USER {sortConfig.key === 'username' && <ArrowUpDown size={12} className={sortConfig.direction === 'asc' ? 'rotate-180' : ''}/>}</div><ResizeHandle id="user"/></th>
                            <th className="p-4" style={{width: colWidths.email}}><div className="flex items-center gap-1"><Mail size={12}/> E-MAIL</div><ResizeHandle id="email"/></th>
                            <th className="p-4" style={{width: colWidths.actions}}>AKTIONEN <ResizeHandle id="actions"/></th>
                            <th className="p-4" style={{width: colWidths.bio}}>BIOGRAFIE <ResizeHandle id="bio"/></th>
                            <th className="p-4 cursor-pointer" style={{width: colWidths.follower}} onClick={() => requestSort('followersCount')}><div className="flex items-center gap-1">FOLLOWER {sortConfig.key === 'followersCount' && <ArrowUpDown size={12} className={sortConfig.direction === 'asc' ? 'rotate-180' : ''}/>}</div><ResizeHandle id="follower"/></th>
                            <th className="p-4 cursor-pointer" style={{width: colWidths.date}} onClick={() => requestSort('foundDate')}><div className="flex items-center gap-1">DATUM {sortConfig.key === 'foundDate' && <ArrowUpDown size={12} className={sortConfig.direction === 'asc' ? 'rotate-180' : ''}/>}</div><ResizeHandle id="date"/></th>
                            <th className="p-4 cursor-pointer" style={{width: colWidths.lastScan}} onClick={() => requestSort('lastScrapedDate')}><div className="flex items-center gap-1">LETZTER SCAN {sortConfig.key === 'lastScrapedDate' && <ArrowUpDown size={12} className={sortConfig.direction === 'asc' ? 'rotate-180' : ''}/>}</div><ResizeHandle id="lastScan"/></th>
                        </tr>
                    </thead>
                    <tbody className="divide-y divide-slate-100 text-sm">
                        {paginatedUsers.map((user) => {
                            const isS = selectedUsers.includes(user.pk);
                            const isG = user.isGerman;
                            const isNG = user.isGerman === false;
                            const isGone = !!user.notFoundDate; // Profil existiert nicht (mehr)
                            // Hintergrund-Prioritaet: gone > selected > german > non-german
                            const rowBg = isGone
                                ? 'bg-red-200/70 hover:bg-red-200/90'
                                : isS ? 'bg-purple-50/50'
                                : isG ? 'bg-yellow-100/40'
                                : isNG ? 'bg-red-50/30'
                                : '';
                            return (
                                <tr key={user.pk} className={`group transition-all hover:bg-green-50/20 ${rowBg}`}>
                                    <td className="p-4 text-center"><input type="checkbox" checked={isS} onChange={() => toggleSelectUser(user.pk)} className="w-4 h-4 accent-purple-600"/></td>
                                    <td className="p-4 align-top">
                                        <div className="flex items-center gap-3">
                                            {/* Avatar: Fest fixiert auf 40x40 Pixel, kein Schrumpfen, perfekter Kreis */}
                                            <div className="w-10 h-10 rounded-full bg-slate-200 flex-shrink-0 flex items-center justify-center font-black text-slate-500 text-sm uppercase">
                                                {user.username[0]}
                                            </div>
                                            <div className="min-w-0">
                                                <div className="font-black text-slate-900 leading-tight">
                                                    <a href={`https://instagram.com/${user.username}`} target="_blank" className="text-xl hover:text-purple-600 transition-all hover:underline decoration-2">
                                                        {user.username}
                                                    </a>
                                                    {isG && <span className="ml-2 text-lg">🇩🇪</span>}
                                                    {isNG && <span className="ml-2 text-lg">✘</span>}
                                                </div>
                                                <div className="text-sm text-slate-500 font-medium mt-0.5">{user.fullName}</div>
                                                <div className="text-[9px] text-slate-300 font-bold uppercase mt-1 tracking-wider">Src: {user.sourceAccount}</div>
                                                {user.status === 'new' && <span className="inline-block mt-1.5 bg-purple-600 text-white text-[9px] px-2 py-0.5 rounded font-black tracking-widest">NEU</span>}
                                                {isGone && (
                                                    <div
                                                        className="inline-flex items-center gap-1 mt-1.5 bg-red-600 text-white text-[9px] px-2 py-0.5 rounded font-black tracking-widest border border-red-700 shadow-sm"
                                                        title={`Beim letzten Scan am ${formatDate(user.notFoundDate)} war dieses Profil nicht erreichbar`}
                                                    >
                                                        <XCircle size={10}/> EXISTIERT NICHT — SCAN {formatDate(user.notFoundDate)}
                                                    </div>
                                                )}
                                                {user.lastExported && (
                                                    <div className="inline-flex items-center gap-1 mt-1.5 ml-1 bg-green-100 text-green-700 text-[9px] px-2 py-0.5 rounded font-black tracking-widest border border-green-200" title={`Exportiert am ${formatDate(user.lastExported)}`}>
                                                        <Download size={10}/> EXPORTIERT {formatDate(user.lastExported)}
                                                    </div>
                                                )}
                                                {user.germanCheckResult && (isG || isNG) && <div className="text-[10px] font-bold text-slate-500 mt-1.5 bg-slate-50 p-1 rounded border border-slate-100">{user.germanCheckResult}</div>}
                                            </div>
                                        </div>
                                    </td>
                                    <td className="p-4 align-top">
                                        {(() => {
                                            const emailRegex = /[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}/;
                                            const fromField = (user.email || '').match(emailRegex)?.[0];
                                            const fromBio = !fromField ? (user.bio || '').match(emailRegex)?.[0] : null;
                                            const mail = fromField || fromBio;
                                            if (!mail) {
                                                return <span className="text-slate-300 text-xs font-medium">—</span>;
                                            }
                                            return (
                                                <div className="flex items-center gap-2 min-w-0">
                                                    <a
                                                        href={`mailto:${mail}`}
                                                        className="text-sm font-medium text-blue-600 hover:text-blue-800 hover:underline truncate"
                                                        title={mail}
                                                    >
                                                        {mail}
                                                    </a>
                                                    <button
                                                        onClick={(e) => {
                                                            e.preventDefault();
                                                            navigator.clipboard.writeText(mail);
                                                        }}
                                                        className="p-1 rounded border border-slate-200 text-slate-400 hover:bg-slate-100 hover:text-slate-700 flex-shrink-0"
                                                        title="E-Mail kopieren"
                                                    >
                                                        <Mail size={12}/>
                                                    </button>
                                                    {fromBio && (
                                                        <span className="text-[9px] font-bold text-slate-400 bg-slate-100 px-1.5 py-0.5 rounded uppercase tracking-wider flex-shrink-0" title="Aus Bio extrahiert">BIO</span>
                                                    )}
                                                </div>
                                            );
                                        })()}
                                    </td>
                                    <td className="p-4 align-top">
                                        <div className="flex gap-1">
                                            <button onClick={() => handleStatusChange(user.pk, user.status === 'favorite' ? 'active' : 'favorite')} className={`p-2 rounded border transition-all ${user.status === 'favorite' ? 'bg-green-500 border-green-600 text-white shadow-md' : 'bg-white text-green-500 border-green-100 hover:bg-green-50'}`} title="Favorit"><Heart size={16} className={user.status === 'favorite' ? 'fill-white' : ''}/></button>
                                            <button onClick={() => handleStatusChange(user.pk, user.status === 'eng' ? 'active' : 'eng')} className={`p-2 rounded border transition-all ${user.status === 'eng' ? 'bg-blue-500 border-blue-600 text-white shadow-md' : 'bg-white text-blue-500 border-blue-100 hover:bg-blue-50'}`} title="English"><Globe size={16}/></button>
                                            <button onClick={() => handleStatusChange(user.pk, 'blocked')} className="p-2 bg-white border border-red-100 rounded text-red-500 hover:bg-red-500 hover:text-white transition-all" title="Blockieren"><Ban size={16}/></button>
                                            <button onClick={() => handleStatusChange(user.pk, user.status === 'hidden' ? 'active' : 'hidden')} className={`p-2 rounded border transition-all ${user.status === 'hidden' ? 'bg-orange-500 border-orange-600 text-white' : 'bg-white text-orange-500 border-orange-100 hover:bg-orange-50'}`} title="Verstecken"><EyeOff size={16}/></button>
                                        </div>
                                    </td>
                                    <td className="p-4 align-top text-slate-600 truncate">{user.bio}</td>
                                    <td className="p-4 align-top font-bold text-blue-600">{user.followersCount?.toLocaleString()}</td>
                                    <td className="p-4 align-top text-xs text-slate-400">{formatDate(user.foundDate)}</td>
                                    <td className="p-4 align-top text-xs">
                                        {(() => {
                                            // Bestes verfuegbares Scan-Datum nehmen.
                                            // Vorrang: lastScrapedDate (genau), dann notFoundDate (impliziert Scan), sonst nichts.
                                            const scanIso = user.lastScrapedDate || user.notFoundDate;
                                            if (scanIso) {
                                                const isApprox = !user.lastScrapedDate && !!user.notFoundDate;
                                                return (
                                                    <div className="flex flex-col">
                                                        <span className="text-slate-600 font-bold">{formatDate(scanIso)}</span>
                                                        <span className="text-[10px] text-slate-400">
                                                            {new Date(scanIso).toLocaleTimeString('de-DE', { hour: '2-digit', minute: '2-digit' })} Uhr
                                                        </span>
                                                        {isApprox && <span className="text-[9px] text-amber-600 font-bold mt-0.5">~ ungefähr</span>}
                                                    </div>
                                                );
                                            }
                                            // Kein Datum, aber DACH-Check vorhanden -> wurde mal gescannt vor dem Update
                                            if (user.germanCheckResult) {
                                                return <span className="text-[10px] text-slate-400 italic">schon gescannt<br/>(kein Datum)</span>;
                                            }
                                            return <span className="text-slate-300 italic">noch nie</span>;
                                        })()}
                                    </td>
                                </tr>
                            );
                        })}
                    </tbody>
                </table>
            </div>
            {totalPages > 1 && (
                <div className="flex items-center justify-center gap-4 py-8">
                    <button disabled={currentPage === 1} onClick={() => setCurrentPage(prev => Math.max(1, prev - 1))} className="p-2 border rounded hover:bg-white disabled:opacity-30"><ArrowUpDown className="rotate-90" size={18} /></button>
                    <span className="text-sm font-bold">Seite {currentPage} von {totalPages}</span>
                    <button disabled={currentPage === totalPages} onClick={() => setCurrentPage(prev => Math.min(totalPages, prev + 1))} className="p-2 border rounded hover:bg-white disabled:opacity-30"><ArrowUpDown className="-rotate-90" size={18} /></button>
                </div>
            )}
            </>
        )}
      </main>
    </div>
  );
}
