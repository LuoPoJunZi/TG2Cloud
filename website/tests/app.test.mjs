import test from 'node:test';
import assert from 'node:assert/strict';
import {readFile} from 'node:fs/promises';
import {runInNewContext} from 'node:vm';

const script=await readFile(new URL('../public/assets/app.js',import.meta.url),'utf8');

function fixture(){
  const deferred=[];
  class Element{
    constructor(){this.listeners={};this.open=false;this.value='';this.isConnected=true;this.dataset={};}
    addEventListener(name,handler){(this.listeners[name]??=[]).push(handler);}
    emit(name,event={}){for(const handler of this.listeners[name]||[])handler(event);}
    setAttribute(){}
    matches(){return false;}
    getClientRects(){return [1];}
    focus(){document.activeElement=this;}
    showModal(){this.open=true;}
    close(){this.open=false;deferred.push(()=>this.emit('close'));}
    replaceChildren(){}
  }
  const elements=new Map(['.theme-toggle','#mobile-nav-dialog','#search-dialog','#search-input',
    '#search-results','.search-status','[data-close-nav]','[data-close-search]',
    '.mobile-nav-toggle','[data-open-search]','.back-to-top'].map(key=>[key,new Element()]));
  const classes=new Set();
  const body={classList:{add:value=>classes.add(value),toggle:(value,on)=>on?classes.add(value):classes.delete(value)}};
  const document=new Element();
  document.documentElement=new Element();document.body=body;document.activeElement=new Element();
  document.querySelector=selector=>elements.get(selector)||null;
  document.querySelectorAll=selector=>['.mobile-nav-toggle','[data-open-search]'].includes(selector)?[elements.get(selector)]:[];
  const window={matchMedia:()=>({matches:false,addEventListener(){}}),addEventListener(){}};
  runInNewContext(script,{document,window,HTMLElement:Element,setTimeout,clearTimeout,
    localStorage:{getItem(){return null;}},fetch:async()=>({ok:true,json:async()=>[]})});
  return {document,elements,classes,flush:()=>{while(deferred.length)deferred.shift()();}};
}

test('navigation close event must not unlock the background or steal focus from search',async()=>{
  const state=fixture(),get=key=>state.elements.get(key);
  get('.mobile-nav-toggle').focus();get('.mobile-nav-toggle').emit('click');
  assert.ok(get('#mobile-nav-dialog').open);
  state.document.emit('keydown',{key:'k',ctrlKey:true,target:get('.mobile-nav-toggle'),preventDefault(){}});
  assert.ok(get('#search-dialog').open);
  state.flush();
  await new Promise(resolve=>setImmediate(resolve));
  assert.equal(get('#mobile-nav-dialog').open,false);
  assert.ok(state.classes.has('no-scroll'),'search remains modal after navigation closes asynchronously');
  assert.equal(state.document.activeElement,get('#search-input'),'closing previous dialog must not move focus');
});

test('closing the final search dialog releases scroll and restores its own trigger',async()=>{
  const state=fixture(),get=key=>state.elements.get(key);
  const trigger=get('[data-open-search]');
  trigger.focus();trigger.emit('click');
  await new Promise(resolve=>setImmediate(resolve));
  assert.equal(state.document.activeElement,get('#search-input'));
  get('[data-close-search]').emit('click');state.flush();
  assert.equal(get('#search-dialog').open,false);
  assert.equal(state.classes.has('no-scroll'),false);
  assert.equal(state.document.activeElement,trigger);
});
