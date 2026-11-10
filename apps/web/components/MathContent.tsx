'use client';
import {useEffect,useState} from 'react';
import DOMPurify from 'dompurify';

/** Never server-render untrusted HTML; sanitize on the client as a final defense. */
export function MathContent({html,empty='Not available'}:{html?:string;empty?:string}) {
  const [safe,setSafe]=useState('');
  useEffect(()=>{
    const clean=DOMPurify.sanitize(html||'',{USE_PROFILES:{html:true,mathMl:true},FORBID_TAGS:['img','svg','script','iframe','style'],FORBID_ATTR:['style','onerror','onclick','onload']});
    setSafe(clean);
  },[html]);
  if(!html)return <div className="empty-content">{empty}</div>;
  if(!safe)return <div className="content-loading" aria-label="Preparing safe question content">Preparing question…</div>;
  return <div className="math-content" dangerouslySetInnerHTML={{__html:safe}}/>;
}
