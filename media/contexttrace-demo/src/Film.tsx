import React, {CSSProperties} from 'react';
import {AbsoluteFill, Audio, Easing, interpolate, Sequence, staticFile, useCurrentFrame} from 'remotion';
import {loadFont} from '@remotion/fonts';

loadFont({family: 'Manrope', url: staticFile('fonts/Manrope.ttf'), weight: '200 800'});

const C = {paper: '#F4F3EE', ink: '#172522', soft: '#77807A', mint: '#BFE7CD', green: '#386952', line: '#D9DDD4', red: '#A54D3B'};
const ease = Easing.bezier(0.16, 1, 0.3, 1);
const ramp = (f: number, a: number, b: number) => interpolate(f, [a, b], [0, 1], {extrapolateLeft: 'clamp', extrapolateRight: 'clamp', easing: ease});
const enter = (f: number, delay = 0): CSSProperties => ({opacity: ramp(f, delay, delay + 22), transform: `translateY(${(1-ramp(f, delay, delay+30))*28}px)`});
const mono = '"SFMono-Regular", Consolas, "Liberation Mono", monospace';

function Mark({size = 48, color = C.ink}: {size?: number; color?: string}) {
  return <svg width={size} height={size} viewBox="0 0 64 64" fill="none"><path d="M45 13H28C17 13 11 21 11 32s6 19 17 19h17" stroke={color} strokeWidth="5" strokeLinecap="round"/><path d="M27 32h23" stroke={color} strokeWidth="5" strokeLinecap="round"/><circle cx="28" cy="32" r="6" fill={color}/><circle cx="50" cy="32" r="6" fill={color}/></svg>;
}
function Brand({dark = false}: {dark?: boolean}) {
  return <div style={{display:'flex', gap:14, alignItems:'center', fontSize:27, fontWeight:650, letterSpacing:-1, color:dark?C.paper:C.ink}}><Mark size={37} color={dark?C.mint:C.ink}/>ContextTrace</div>;
}
function Kicker({children, color=C.soft}: {children:React.ReactNode; color?:string}) {
  return <div style={{fontSize:19, fontWeight:650, letterSpacing:3.5, textTransform:'uppercase', color}}>{children}</div>;
}
function Check({size=26, color=C.green}: {size?:number; color?:string}) {
  return <svg width={size} height={size} viewBox="0 0 24 24" fill="none"><path d="m5 12 4 4L19 6" stroke={color} strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round"/></svg>;
}
function Footer({step, dark=false}: {step:string; dark?:boolean}) {
  return <div style={{position:'absolute', bottom:48, left:100, right:100, display:'flex', justifyContent:'space-between', color:dark?'#90A49B':C.soft, fontSize:17, letterSpacing:0.3}}><span>ILLUSTRATED WORKFLOW · FICTIONAL DEMO</span><span>{step}</span></div>;
}
function Scene({children, duration, background=C.paper, fadeOut=true, fadeIn=true}: {children:React.ReactNode; duration:number; background?:string; fadeOut?:boolean; fadeIn?:boolean}) {
  const f=useCurrentFrame();
  const entrance=fadeIn?interpolate(f,[0,12],[0,1],{extrapolateLeft:'clamp',extrapolateRight:'clamp'}):1;
  return <AbsoluteFill style={{background, opacity: entrance*(fadeOut?interpolate(f,[duration-12,duration],[1,0],{extrapolateLeft:'clamp',extrapolateRight:'clamp'}):1)}}>{children}</AbsoluteFill>;
}

function Opening() {
  const f=useCurrentFrame();
  return <Scene duration={117} background={C.ink} fadeIn={false}>
    <div style={{position:'absolute', inset:0, background:'radial-gradient(ellipse at 70% 110%, #294D3F 0%, transparent 62%)'}}/>
    <div style={{position:'absolute', top:70, left:100}}><Brand dark/></div>
    <div style={{position:'absolute', top:330, left:190, right:150}}>
      <div style={{...enter(f,3), fontSize:100, fontWeight:500, lineHeight:1.17, letterSpacing:-5, color:C.paper}}>An answer is only as good</div>
      <div style={{...enter(f,20), fontSize:100, fontWeight:500, lineHeight:1.17, letterSpacing:-5, color:C.paper}}>as its <span style={{color:C.mint}}>evidence.</span></div>
      <div style={{marginTop:42, height:2, width:interpolate(ramp(f,35,78),[0,1],[0,340]), background:C.mint, opacity:0.65}}/>
    </div>
    <div style={{position:'absolute', bottom:65, right:100, fontSize:18, letterSpacing:4, color:'#93AAA0'}}>MEET CONTEXTTRACE</div>
  </Scene>;
}
function Introduction() {
  const f=useCurrentFrame();
  const p=ramp(f,8,75);
  return <Scene duration={102}>
    <div style={{position:'absolute', top:265, width:'100%', display:'flex', flexDirection:'column', alignItems:'center'}}>
      <div style={{...enter(f), display:'flex', gap:30, alignItems:'center'}}><Mark size={110}/><div style={{fontSize:116, fontWeight:600, letterSpacing:-7}}>ContextTrace</div></div>
      <div style={{...enter(f,12), fontSize:35, marginTop:25, color:'#65736A'}}>Follow the answer. Find the evidence.</div>
      <svg width="980" height="190" style={{marginTop:55}} viewBox="0 0 980 190">
        <path d="M90 65H890" stroke={C.line} strokeWidth="2"/>
        <path d="M90 65H890" stroke={C.green} strokeWidth="3" strokeDasharray="800" strokeDashoffset={800*(1-p)}/>
        {['Question','Evidence','Answer'].map((label,i)=><g key={label}><circle cx={90+i*400} cy={65} r={12} fill={p>=i*0.5?C.green:C.paper} stroke={C.green} strokeWidth="2"/><text x={90+i*400} y={122} textAnchor="middle" style={{fontFamily:'Manrope',fontSize:23,fill:C.soft}}>{label}</text></g>)}
      </svg>
    </div>
  </Scene>;
}
function Comparison() {
  const f=useCurrentFrame();
  return <Scene duration={237}>
    <div style={{position:'absolute', left:100, top:60}}><Brand/></div>
    <div style={{position:'absolute', left:160, top:150, ...enter(f)}}>
      <Kicker>01 / Inspect</Kicker>
      <div style={{fontSize:72,fontWeight:500,letterSpacing:-3.5,marginTop:18}}>A confident answer. A different source.</div>
    </div>
    <div style={{position:'absolute', top:325, left:160, right:160, display:'flex', gap:32}}>
      <div style={{...enter(f,10), flex:1, height:410, padding:48, background:'#FFFFFF', borderRadius:26, border:'1px solid #E2E3DD', boxShadow:'0 25px 65px #17252207'}}>
        <Kicker>AI answer</Kicker>
        <div style={{fontSize:26,color:C.soft,marginTop:26}}>Page the on-call engineer above</div>
        <div style={{fontSize:136,letterSpacing:-8,fontWeight:500,lineHeight:1.35,color:f>75?C.red:C.ink}}>4<span style={{fontSize:70}}>%</span></div>
        <div style={{fontSize:24,color:C.soft}}>error rate</div>
      </div>
      <div style={{...enter(f,35), flex:1, height:410, padding:48, background:'#E8EDE4', borderRadius:26, border:'1px solid #D6DED1'}}>
        <div style={{display:'flex',justifyContent:'space-between'}}><Kicker color={C.green}>Selected source</Kicker><span style={{fontSize:18,color:C.green}}>nimbus-alerts.md</span></div>
        <div style={{fontSize:26,color:C.soft,marginTop:26}}>Page the on-call engineer above</div>
        <div style={{fontSize:136,letterSpacing:-8,fontWeight:500,lineHeight:1.35,color:C.green}}>2<span style={{fontSize:70}}>%</span></div>
        <div style={{fontSize:24,color:C.soft}}>error rate</div>
      </div>
    </div>
    <div style={{...enter(f,90), position:'absolute', left:160, top:800, display:'flex', gap:22, alignItems:'center'}}>
      <div style={{padding:'15px 26px',background:'#F0DED6',color:C.red,borderRadius:40,fontSize:23,fontWeight:650}}>Contradicted</div>
      <div style={{fontSize:27,color:'#627168'}}>The claim conflicts with its cited evidence.</div>
    </div>
    <Footer step="ANSWER → SOURCE"/>
  </Scene>;
}
function Repair() {
  const f=useCurrentFrame();
  return <Scene duration={177} background={C.ink}>
    <div style={{position:'absolute', inset:0, background:'radial-gradient(ellipse at 90% 40%, #294438 0%, transparent 65%)'}}/>
    <div style={{position:'absolute',left:100,top:60}}><Brand dark/></div>
    <div style={{position:'absolute',left:160,top:185,width:640,...enter(f)}}>
      <Kicker color="#9AB4A6">02 / Fix & verify</Kicker>
      <div style={{fontSize:88,fontWeight:500,lineHeight:1.13,letterSpacing:-4.5,color:C.paper,marginTop:30}}>Fix the answer.<br/><span style={{color:C.mint}}>Check it again.</span></div>
      <div style={{...enter(f,23),fontSize:30,lineHeight:1.55,color:'#A9BBB1',marginTop:38,width:560}}>Use the source value.<br/>Verify the corrected trace.</div>
    </div>
    <div style={{...enter(f,20),position:'absolute',left:935,top:210,width:760,padding:48,border:'1px solid #597265',background:'#FFFFFF06',borderRadius:26}}>
      <Kicker color="#9AB4A6">Corrected answer</Kicker>
      <div style={{fontSize:35,lineHeight:1.6,color:C.paper,marginTop:38}}>Nimbus pages the on-call engineer when errors exceed</div>
      <div style={{fontSize:136,fontWeight:500,letterSpacing:-6,color:C.mint,lineHeight:1.5}}>2<span style={{fontSize:70}}>%</span></div>
      <div style={{height:1,background:'#597265',marginBottom:28}}/>
      <div style={{...enter(f,65),display:'flex',alignItems:'center',gap:14,fontSize:27,color:C.mint}}><Check color={C.mint}/>Supported by the selected source</div>
    </div>
    <Footer step="FIX → RECHECK" dark/>
  </Scene>;
}
function Regression() {
  const f=useCurrentFrame();
  return <Scene duration={177}>
    <div style={{position:'absolute',left:100,top:60}}><Brand/></div>
    <div style={{position:'absolute',left:160,top:190,width:570,...enter(f)}}>
      <Kicker>03 / Prevent regressions</Kicker>
      <div style={{fontSize:84,lineHeight:1.15,letterSpacing:-4,fontWeight:500,marginTop:30}}>Keep the fix<br/>in your CI.</div>
      <div style={{...enter(f,20),fontSize:29,color:'#65736A',lineHeight:1.55,marginTop:38}}>Save the case.<br/>Catch the failure if it returns.</div>
    </div>
    <div style={{...enter(f,10),position:'absolute',left:825,top:205,width:925,height:575,borderRadius:26,background:C.ink,boxShadow:'0 35px 75px #17252217',overflow:'hidden'}}>
      <div style={{height:70,borderBottom:'1px solid #FFFFFF15',display:'flex',alignItems:'center',padding:'0 32px',gap:10}}>{[0,1,2].map(i=><div key={i} style={{width:11,height:11,borderRadius:'50%',background:'#5B7165'}}/>)}<span style={{marginLeft:18,color:'#A6B8AC',fontSize:18}}>ContextTrace · saved regression case</span></div>
      <div style={{padding:'34px 36px',fontFamily:mono,fontSize:23,lineHeight:1.8,color:'#EDF1E9'}}>
        <div style={{color:'#A5CFB5'}}>$ python examples/investigations/run.py \</div>
        <div style={{paddingLeft:26}}>--case ci-debugging-walkthrough</div>
        <div style={{...enter(f,38),color:'#A6B8AC',marginTop:24}}>{'"summary": {'}<br/>&nbsp; {'"case_count": 1,'}<br/>&nbsp; {'"trace_count": 2,'}<br/>&nbsp; {'"check_count": 4,'}<br/>&nbsp; <span style={{color:C.mint}}>{'"passed": true'}</span><br/>{'}'}</div>
      </div>
    </div>
    <div style={{...enter(f,65),position:'absolute',left:850,top:824,display:'flex',gap:13,alignItems:'center',fontSize:23,color:C.green}}><Check/>2 traces. 4 checks. Passing locally.</div>
    <Footer step="SAVE → REPLAY"/>
  </Scene>;
}
function Closing() {
  const f=useCurrentFrame();
  return <Scene duration={210} fadeOut={false}>
    <div style={{position:'absolute',inset:0,background:'radial-gradient(ellipse at 50% 110%, #DDE8D7 0%, transparent 68%)'}}/>
    <div style={{position:'absolute',top:190,left:0,right:0,display:'flex',flexDirection:'column',alignItems:'center'}}>
      <div style={{...enter(f,2),display:'flex',alignItems:'center',gap:26}}><Mark size={96}/><span style={{fontSize:105,fontWeight:600,letterSpacing:-6}}>ContextTrace</span></div>
      <div style={{...enter(f,15),fontSize:50,letterSpacing:-1.8,marginTop:28}}>Make every answer inspectable.</div>
      <div style={{...enter(f,30),display:'flex',gap:30,alignItems:'center',fontSize:25,color:'#617067',marginTop:48}}><span>Local-first</span><span style={{color:'#9BAA9B'}}>·</span><span>Open source</span><span style={{color:'#9BAA9B'}}>·</span><span>Built for developers</span></div>
      <div style={{...enter(f,43),fontFamily:mono,fontSize:29,marginTop:55,padding:'25px 42px',background:C.ink,color:C.paper,borderRadius:16,boxShadow:'0 15px 40px #17252212'}}><span style={{color:'#91AC9A',marginRight:19}}>$</span>pip install contexttrace</div>
      <div style={{...enter(f,52),fontSize:22,color:'#617067',marginTop:28}}>github.com/samarth1412/Context-Trace</div>
    </div>
    <div style={{position:'absolute',bottom:54,width:'100%',textAlign:'center',fontSize:19,color:'#778078'}}>Created by Samarth Vinayaka</div>
  </Scene>;
}

export function Film() {
  return <AbsoluteFill style={{fontFamily:'Manrope, sans-serif',color:C.ink,background:C.paper}}>
    <style>{'* {box-sizing: border-box;}'}</style>
    <Audio src={staticFile('soundtrack.wav')} volume={0.85}/>
    <Sequence from={0} durationInFrames={117}><Opening/></Sequence>
    <Sequence from={105} durationInFrames={102}><Introduction/></Sequence>
    <Sequence from={195} durationInFrames={237}><Comparison/></Sequence>
    <Sequence from={420} durationInFrames={177}><Repair/></Sequence>
    <Sequence from={585} durationInFrames={177}><Regression/></Sequence>
    <Sequence from={750} durationInFrames={210}><Closing/></Sequence>
  </AbsoluteFill>;
}
