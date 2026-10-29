'use client';
import { useCallback, useEffect, useState } from 'react';

// Thema (licht/donker) en taal (nl/en) worden per browser onthouden. Het scriptje in <head> zet ze vóór het eerste scherm,
// zodat er geen flits van het verkeerde thema is.
export const SETTINGS_SCRIPT = "try{var t=localStorage.getItem('mi_theme'),l=localStorage.getItem('mi_lang');document.documentElement.dataset.theme=t==='dark'?'dark':'light';document.documentElement.lang=l==='en'?'en':'nl'}catch(e){document.documentElement.dataset.theme='light'}";

export function useSettings() {
  const [theme, setThemeState] = useState('light');
  const [lang, setLangState] = useState('nl');
  useEffect(() => {
    try {
      setThemeState(localStorage.getItem('mi_theme') === 'dark' ? 'dark' : 'light');
      setLangState(localStorage.getItem('mi_lang') === 'en' ? 'en' : 'nl');
    } catch { /* opslag niet beschikbaar */ }
  }, []);
  const setTheme = useCallback((v) => {
    setThemeState(v);
    try { localStorage.setItem('mi_theme', v); } catch { /* */ }
    document.documentElement.dataset.theme = v;
  }, []);
  const setLang = useCallback((v) => {
    setLangState(v);
    try { localStorage.setItem('mi_lang', v); } catch { /* */ }
    document.documentElement.lang = v;
  }, []);
  return { theme, lang, setTheme, setLang };
}
