'use client';

import { useEffect } from 'react';

const KEY='marketintel_portfolio';

function readPortfolio(){try{return JSON.parse(localStorage.getItem(KEY)||'[]')}catch{return[]}}
function writePortfolio(rows){localStorage.setItem(KEY,JSON.stringify(rows));window.dispatchEvent(new Event('marketintel-portfolio-change'));}
function parsePrice(text){const m=String(text||'').match(/\$([0-9,]+(?:\.[0-9]+)?)/);return m?Number(m[1].replaceAll(',','')):null}
function parseTicker(text){return String(text||'').split(':')[0].trim().toUpperCase()}

function injectPortfolioNav(){
  const nav=document.querySelector('.sidebar nav');
  if(!nav||nav.querySelector('[data-portfolio-nav]'))return;
  const link=document.createElement('a');
  link.href='/portfolio';
  link.className='navItem';
  link.dataset.portfolioNav='true';
  link.innerHTML='<span style="width:16px;display:inline-grid;place-items:center;font-size:14px">▣</span>Portfolio';
  nav.appendChild(link);
}

function styleButton(button){
  Object.assign(button.style,{display:'inline-flex',alignItems:'center',justifyContent:'center',gap:'8px',marginTop:'12px',padding:'10px 14px',border:'1px solid #2c8b64',borderRadius:'9px',background:'linear-gradient(180deg,#174b37,#102b20)',color:'#e0fff0',fontWeight:'700',fontSize:'13px',cursor:'pointer',boxShadow:'0 0 24px rgba(53,229,160,.07)'});
}

function injectAddControl(){
  const panel=document.querySelector('.detailPanelOpportunity');
  if(!panel||panel.querySelector('[data-add-portfolio]'))return;
  const signal=panel.querySelector('.detailScore .signal');
  if(!signal||!signal.classList.contains('alert'))return;
  const title=panel.querySelector('.detailTop h2');
  const ticker=parseTicker(title?.textContent);
  const price=parsePrice(panel.querySelector('.detailTicker')?.textContent);
  const company=String(panel.querySelector('.detailTicker')?.textContent||'').split('·')[0].trim();
  if(!ticker||price==null)return;

  const wrap=document.createElement('div');
  wrap.dataset.portfolioControl='true';
  wrap.style.cssText='margin-top:12px;padding:12px;border:1px solid #223b32;border-radius:10px;background:#0b1512;display:flex;align-items:center;gap:10px;flex-wrap:wrap;';
  const button=document.createElement('button');
  button.type='button';button.dataset.addPortfolio='true';button.textContent='＋ Voeg toe aan portfolio';styleButton(button);
  button.style.marginTop='0';
  button.onclick=()=>{
    if(wrap.querySelector('input'))return;
    button.style.display='none';
    wrap.innerHTML='';
    const label1=document.createElement('label');label1.textContent='Aantal';label1.style.cssText='color:#708295;font-size:11px;font-weight:700;display:flex;flex-direction:column;gap:5px;';
    const qty=document.createElement('input');qty.type='number';qty.min='0.0001';qty.step='any';qty.value='1';qty.style.cssText='width:90px;padding:8px 9px;background:#0d1820;border:1px solid #2a3b4d;border-radius:7px;color:#eaf1f5;outline:none;';label1.appendChild(qty);
    const label2=document.createElement('label');label2.textContent='Aankoopprijs';label2.style.cssText=label1.style.cssText;
    const entry=document.createElement('input');entry.type='number';entry.min='0.01';entry.step='0.01';entry.value=price.toFixed(2);entry.style.cssText=qty.style.cssText;label2.appendChild(entry);
    const save=document.createElement('button');save.type='button';save.textContent='Opslaan';styleButton(save);save.style.marginTop='17px';
    const cancel=document.createElement('button');cancel.type='button';cancel.textContent='Annuleren';cancel.style.cssText='margin-top:17px;padding:9px 12px;border:1px solid #2a3b4d;border-radius:8px;background:#101923;color:#8da0b2;font-weight:700;cursor:pointer;';
    wrap.append(label1,label2,save,cancel);
    cancel.onclick=()=>{wrap.replaceChildren(button);button.style.display='inline-flex';};
    save.onclick=()=>{
      const q=Number(qty.value),p=Number(entry.value);
      if(!(q>0&&p>0))return;
      const rows=readPortfolio();
      const existing=rows.find(x=>x.ticker===ticker);
      if(existing){const totalQty=Number(existing.quantity)+q;existing.entryPrice=((Number(existing.entryPrice)*Number(existing.quantity))+(p*q))/totalQty;existing.quantity=totalQty;existing.updatedAt=new Date().toISOString();}
      else rows.push({ticker,company,quantity:q,entryPrice:p,entryScore:null,addedAt:new Date().toISOString(),updatedAt:new Date().toISOString()});
      const row=rows.find(x=>x.ticker===ticker);if(row&&!row.entryScore){const scoreText=panel.querySelector('.detailScore strong')?.textContent||'';row.entryScore=Number(scoreText.replace(/[^0-9.]/g,''))||null;}
      writePortfolio(rows);window.location.href='/portfolio';
    };
  };
  wrap.appendChild(button);
  const scoreBox=panel.querySelector('.detailScore');
  scoreBox?.after(wrap);
}

export default function PortfolioBridge(){
  useEffect(()=>{
    const run=()=>{injectPortfolioNav();injectAddControl();};
    run();
    const observer=new MutationObserver(run);
    observer.observe(document.body,{childList:true,subtree:true});
    return()=>observer.disconnect();
  },[]);
  return null;
}
