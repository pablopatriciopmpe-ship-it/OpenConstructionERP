import{u as W,i as H,r,j as e,L as A}from"./vendor-react-Ds644eE6.js";import{a0 as K,eV as Q,c$ as X,d6 as y,eS as Z,d as ee,a1 as te,bH as ae,P as se,aI as re,c as ne,eW as oe,ap as ie,aX as le,eX as ce,G as de,dO as E,W as F,eY as me,ch as L,c8 as ue,et as ge,aZ as xe,cL as pe,cY as he,K as be,ck as fe,j as ye,ah as R,eZ as ve}from"./index-CFgjPe8O.js";import{u as we}from"./vendor-i18n-DFJuOPeM.js";import"./vendor-dompurify-ChJSIbGG.js";import"./vendor-query-wpw2X9UX.js";import"./vendor-preload-ckwbz45p.js";import"./vendor-recharts-C58zgzh2.js";import"./vendor-flow-BA4JlW4m.js";import"./i18n-en-C_zFozoJ.js";import"./vendor-dnd-1FmqKfd0.js";function ke(t){return t>=500?"unavailable":"credentials"}function je(t,c){return ke(t)==="unavailable"?"unavailable":c?"credentials":"unavailable"}const Ne={blue:{bg:"bg-[#007AFF]/12",fg:"text-[#007AFF]",ring:"ring-[#007AFF]/15"},violet:{bg:"bg-violet-500/10",fg:"text-violet-600",ring:"ring-violet-500/15"},emerald:{bg:"bg-semantic-success/10",fg:"text-semantic-success",ring:"ring-semantic-success/15"},amber:{bg:"bg-semantic-warning/10",fg:"text-semantic-warning",ring:"ring-semantic-warning/15"},rose:{bg:"bg-semantic-error/10",fg:"text-semantic-error",ring:"ring-semantic-error/15"},cyan:{bg:"bg-cyan-500/10",fg:"text-cyan-600",ring:"ring-cyan-500/15"},indigo:{bg:"bg-indigo-500/10",fg:"text-indigo-600",ring:"ring-indigo-500/15"},teal:{bg:"bg-teal-500/10",fg:"text-teal-600",ring:"ring-teal-500/15"}};function De(){const{t,i18n:c}=we(),v=W(),D=H(),w=K(a=>a.setTokens),k=Q(D.search),[m,u]=r.useState(""),[j,g]=r.useState(""),[d,T]=r.useState(!1),[O,N]=r.useState(!1),[_,o]=r.useState(""),[x,B]=r.useState(X),[p,h]=r.useState(!1),[b,M]=r.useState(!0),[S,z]=r.useState(null),[$,q]=r.useState(null),f=r.useRef(null),C=r.useRef(null),P=y.find(a=>a.code===c.language)??y[0];r.useEffect(()=>{u(""),g(""),o("")},[]),r.useEffect(()=>{let a=!1;return(async()=>{try{const s=await fetch("/api/v1/auth/first-run",{headers:{Accept:"application/json"}});if(!s.ok)return;const n=await s.json();a||q(n.demo_enabled!==!1)}catch{}})(),()=>{a=!0}},[]),r.useEffect(()=>{const a=s=>{f.current&&!f.current.contains(s.target)&&h(!1)};return document.addEventListener("mousedown",a),()=>document.removeEventListener("mousedown",a)},[]);const I=r.useCallback(a=>{const s=C.current;if(!s)return;const n=s.getBoundingClientRect();s.style.setProperty("--mx",`${a.clientX-n.left}px`),s.style.setProperty("--my",`${a.clientY-n.top}px`)},[]),G=async a=>{a.preventDefault(),o(""),N(!0);try{const s=await fetch("/api/v1/users/auth/login/",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({email:m,password:j})});if(!s.ok){const l=await s.json().catch(()=>null),i=R(l);if(je(s.status,i)==="unavailable"){o(t("auth.server_unavailable",{defaultValue:"The server did not answer, so your details were never checked. Try again in a moment."}));return}o(i||t("auth.invalid_credentials","Invalid email or password"));return}const n=await s.json();ve(x),w(n.access_token,n.refresh_token,x,m),v(k,{replace:!0})}catch{o(t("auth.connection_error","Unable to connect to server. Please try again."))}finally{N(!1)}},Y=[{email:"demo@openconstructionerp.com",name:"Admin",role:t("auth.demo_role_admin","Administrator"),color:"bg-blue-500",letter:"A"},{email:"manager@openconstructionerp.com",name:"Michael Carter",role:t("auth.demo_role_manager","Manager"),color:"bg-semantic-warning",letter:"M"}],J=async a=>{var s;z(a),o(""),u(""),g("");try{const n=await fetch("/api/v1/users/auth/demo-login/",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({email:a})});if(!n.ok){const i=await n.json().catch(()=>null);if(((s=i==null?void 0:i.detail)==null?void 0:s.error)==="demo_admin_superseded"){o(t("auth.demo_admin_superseded","This installation has an administrator. Please sign in with your own account."));return}const V=R(i);o(V||t("auth.demo_login_failed","Demo login failed. Please try again."));return}const l=await n.json();w(l.access_token,l.refresh_token,!1,a),v(k,{replace:!0})}catch{o(t("auth.connection_error","Unable to connect to server. Please try again."))}finally{z(null)}},U=[{icon:Z,label:t("nav.boq","Bill of Quantities"),stat:"—",hint:t("login.zero_boq","create first BOQ"),tone:"blue"},{icon:ee,label:t("nav.costs","Cost Database"),stat:"—",hint:t("login.zero_costs","import to start"),tone:"cyan"},{icon:te,label:t("nav.assemblies","Assemblies"),stat:"—",hint:t("login.zero_assemblies","no recipes yet"),tone:"violet"},{icon:ae,label:t("nav.catalog","Catalog"),stat:"—",hint:t("login.zero_catalog","add resources"),tone:"indigo"},{icon:se,label:t("nav.takeoff","PDF Takeoff"),stat:"—",hint:t("login.zero_takeoff","upload a drawing"),tone:"amber"},{icon:re,label:t("nav.bim","BIM Viewer"),stat:"—",hint:t("login.zero_bim","no models yet"),tone:"teal"},{icon:ne,label:t("nav.ai_estimate","AI Estimate"),stat:t("login.zero_ai","Ready"),hint:t("login.zero_ai_hint","BETA"),tone:"rose"},{icon:oe,label:t("nav.intelligence","Project IQ"),stat:"—",hint:t("login.zero_iq","awaiting data"),tone:"violet"},{icon:ie,label:t("nav.schedule","4D Schedule"),stat:"—",hint:t("login.zero_schedule","no tasks"),tone:"cyan"},{icon:le,label:t("nav.validation","Validation"),stat:"—",hint:t("login.zero_validation","run checks"),tone:"emerald"}];return e.jsxs("div",{className:"relative min-h-screen w-full overflow-hidden bg-surface-secondary",children:[e.jsx(ce,{}),e.jsx("style",{children:`
        @keyframes oeAuroraSpin {
          0%   { transform: translate(-50%, -50%) rotate(0deg); }
          100% { transform: translate(-50%, -50%) rotate(360deg); }
        }
        @keyframes oeFloat {
          0%, 100% { transform: translateY(0); }
          50%      { transform: translateY(-5px); }
        }
        @keyframes oeShimmer {
          0%   { background-position: -200% 0; }
          100% { background-position: 200% 0; }
        }
        @keyframes oeRingPulse {
          0%   { box-shadow: 0 0 0 0 rgba(16, 185, 129, 0.50); }
          70%  { box-shadow: 0 0 0 10px rgba(16, 185, 129, 0); }
          100% { box-shadow: 0 0 0 0 rgba(16, 185, 129, 0); }
        }

        /* Sky base - very pale, near-white blue. Reads as a bright
           daylight horizon, not a saturated marketing hero. */
        .oe-hero {
          background:
            radial-gradient(120% 90% at 20% 10%,  rgba(224, 242, 254, 0.65) 0%, transparent 60%),
            radial-gradient(110% 80% at 80% 90%,  rgba(219, 234, 254, 0.55) 0%, transparent 60%),
            linear-gradient(160deg, #f8fcff 0%, #f0f9ff 45%, #eaf4ff 100%);
        }
        .dark .oe-hero {
          background:
            radial-gradient(120% 90% at 20% 10%,  rgba(30, 64, 175, 0.45) 0%, transparent 60%),
            radial-gradient(110% 80% at 80% 90%,  rgba(14, 116, 144, 0.45) 0%, transparent 60%),
            linear-gradient(160deg, #0c1929 0%, #0a1628 45%, #061021 100%);
        }

        /* Aurora - soft sky/cyan tint, low opacity so the surface
           stays light and the module tiles read clearly. */
        .oe-aurora {
          position: absolute;
          inset: 0;
          overflow: hidden;
          pointer-events: none;
        }
        .oe-aurora::before,
        .oe-aurora::after,
        .oe-aurora > .oe-aurora-c {
          content: "";
          position: absolute;
          left: 50%;
          top: 50%;
          width: 160vmax;
          height: 160vmax;
          border-radius: 50%;
          filter: blur(80px);
          opacity: 0.40;
          mix-blend-mode: multiply;
          pointer-events: none;
        }
        .dark .oe-aurora::before,
        .dark .oe-aurora::after,
        .dark .oe-aurora > .oe-aurora-c {
          mix-blend-mode: screen;
          opacity: 0.55;
        }
        /* sky-300 - light daylight sky, gentle */
        .oe-aurora::before {
          background: conic-gradient(from 0deg,
            rgba(125, 211, 252, 0.55),
            rgba(186, 230, 253, 0.0),
            rgba(125, 211, 252, 0.0),
            rgba(125, 211, 252, 0.55));
          animation: oeAuroraSpin 38s linear infinite;
        }
        /* cyan-200 - paler haze */
        .oe-aurora::after {
          background: conic-gradient(from 90deg,
            rgba(165, 243, 252, 0.50),
            rgba(125, 211, 252, 0.0),
            rgba(165, 243, 252, 0.0),
            rgba(165, 243, 252, 0.50));
          animation: oeAuroraSpin 52s linear infinite reverse;
        }
        /* blue-200 - soft cloud */
        .oe-aurora > .oe-aurora-c {
          background: conic-gradient(from 200deg,
            rgba(191, 219, 254, 0.50),
            rgba(186, 230, 253, 0.0),
            rgba(191, 219, 254, 0.0),
            rgba(191, 219, 254, 0.50));
          animation: oeAuroraSpin 64s linear infinite;
        }

        /* Mouse spotlight - only renders if --mx/--my are set. */
        .oe-spot {
          position: absolute;
          inset: 0;
          pointer-events: none;
          background: radial-gradient(420px circle at var(--mx, 50%) var(--my, 50%),
            rgba(255, 255, 255, 0.40),
            transparent 60%);
          mix-blend-mode: soft-light;
          opacity: 0.95;
          transition: background 0.05s linear;
        }

        /* Glass module tiles. */
        .oe-tile {
          background:
            linear-gradient(135deg, rgba(255,255,255,0.62) 0%, rgba(255,255,255,0.34) 100%);
          backdrop-filter: blur(22px) saturate(170%);
          -webkit-backdrop-filter: blur(22px) saturate(170%);
          border: 1px solid rgba(255,255,255,0.55);
          box-shadow:
            0 14px 40px -16px rgba(20, 20, 40, 0.18),
            inset 0 1px 0 rgba(255, 255, 255, 0.65);
          transition:
            transform 0.35s cubic-bezier(0.2, 0.8, 0.2, 1),
            box-shadow 0.35s cubic-bezier(0.2, 0.8, 0.2, 1),
            border-color 0.35s ease;
        }
        .dark .oe-tile {
          background:
            linear-gradient(135deg, rgba(255,255,255,0.10) 0%, rgba(255,255,255,0.03) 100%);
          border-color: rgba(255,255,255,0.10);
          box-shadow:
            0 14px 40px -16px rgba(0, 0, 0, 0.55),
            inset 0 1px 0 rgba(255, 255, 255, 0.08);
        }
        .oe-tile:hover {
          transform: translateY(-3px);
          border-color: rgba(0, 122, 255, 0.35);
          box-shadow:
            0 22px 50px -18px rgba(0, 90, 210, 0.30),
            inset 0 1px 0 rgba(255, 255, 255, 0.8);
        }

        /* Lite glass for demo accounts (right side stays solid white,
           but the demo tiles need a touch of glass over the white). */
        .oe-glass-lite {
          background:
            linear-gradient(135deg, rgba(248,250,252,0.95) 0%, rgba(241,245,249,0.85) 100%);
          border: 1px solid rgba(15,23,42,0.06);
          box-shadow:
            0 4px 12px -4px rgba(20, 20, 40, 0.06),
            inset 0 1px 0 rgba(255, 255, 255, 0.9);
        }
        .dark .oe-glass-lite {
          background:
            linear-gradient(135deg, rgba(255,255,255,0.06) 0%, rgba(255,255,255,0.02) 100%);
          border-color: rgba(255,255,255,0.08);
        }

        /* Tiny live-pulse dot. */
        .oe-pulse {
          position: relative;
        }
        .oe-pulse::after {
          content: "";
          position: absolute;
          inset: 0;
          border-radius: inherit;
          animation: oeRingPulse 2.5s cubic-bezier(0.4, 0, 0.6, 1) infinite;
        }

        /* Animated spectrum bar - sky-only palette. */
        .oe-spec-bar {
          background: linear-gradient(90deg,
            rgba(2,132,199,0.95), rgba(14,165,233,0.95), rgba(56,189,248,0.95),
            rgba(2,132,199,0.95));
          background-size: 300% 100%;
          animation: oeShimmer 6s linear infinite;
        }

        .oe-tile-float-a { animation: oeFloat 7s ease-in-out infinite; }
        .oe-tile-float-b { animation: oeFloat 8.5s ease-in-out infinite 1.2s; }

        /* Form pane - solid white, soft shadow, NOT glass. The whole
           right column reads as a clean, paper-white panel for max
           form readability. */
        .oe-form-pane {
          background: #ffffff;
          border: 1px solid rgba(15, 23, 42, 0.06);
          box-shadow:
            0 30px 60px -30px rgba(20, 20, 40, 0.18),
            0 1px 0 rgba(255, 255, 255, 1) inset;
        }
        .dark .oe-form-pane {
          background: #0f172a;
          border-color: rgba(255, 255, 255, 0.06);
          box-shadow:
            0 30px 60px -30px rgba(0, 0, 0, 0.6),
            0 1px 0 rgba(255, 255, 255, 0.04) inset;
        }

        /* Typography - Plus Jakarta Sans for everything, Instrument
           Serif for the editorial headline accent. */
        .oe-font-display {
          font-family: 'Plus Jakarta Sans', system-ui, -apple-system, BlinkMacSystemFont, sans-serif;
          font-feature-settings: 'cv11', 'ss01', 'ss03';
          font-variant-numeric: tabular-nums;
        }
        .oe-font-serif {
          font-family: 'Instrument Serif', 'Iowan Old Style', 'Apple Garamond', Georgia, serif;
          font-feature-settings: 'liga', 'dlig';
          letter-spacing: -0.01em;
        }
      `}),e.jsx("div",{className:"absolute top-4 left-4 z-30",children:e.jsxs("span",{className:"oe-overline inline-flex items-center gap-1.5 rounded-full border border-white/40 bg-white/60 px-2.5 py-1 backdrop-blur-md dark:border-white/10 dark:bg-white/10 dark:text-white/70",children:[e.jsxs("span",{className:"relative flex h-1.5 w-1.5",children:[e.jsx("span",{className:"absolute inline-flex h-full w-full animate-ping rounded-full bg-semantic-warning opacity-75"}),e.jsx("span",{className:"relative inline-flex h-1.5 w-1.5 rounded-full bg-semantic-warning"})]}),"Preview · /login-next"]})}),e.jsxs("div",{className:"absolute top-4 right-4 z-30",ref:f,children:[e.jsxs("button",{onClick:()=>h(!p),className:"flex items-center gap-2 rounded-xl border border-border-light bg-surface-primary px-3.5 py-2.5 text-sm font-medium text-content-secondary hover:bg-surface-secondary hover:border-oe-blue/30 transition-all shadow-sm",children:[e.jsx(de,{size:16,className:"text-content-tertiary"}),e.jsx(E,{code:P.country,size:18}),e.jsx("span",{className:"hidden sm:inline",children:P.name}),e.jsx(F,{size:14,className:`text-content-tertiary transition-transform ${p?"rotate-180":""}`})]}),p&&e.jsx("div",{className:"absolute right-0 mt-2 w-56 max-h-80 overflow-y-auto rounded-xl border border-border-light bg-surface-elevated shadow-xl py-1 animate-stagger-in",children:me(y).map(a=>{const s=c.language===a.code;return e.jsxs("button",{onClick:()=>{c.changeLanguage(a.code),h(!1)},className:`flex w-full items-center gap-2 px-3 py-2 text-sm transition-colors ${s?"bg-oe-blue/10 text-oe-blue font-medium":"text-content-primary hover:bg-surface-secondary"}`,children:[e.jsx(E,{code:a.country,size:16}),e.jsx("span",{className:"truncate",children:a.name})]},a.code)})})]}),e.jsxs("div",{className:"relative z-10 grid min-h-screen grid-cols-1 lg:grid-cols-2",children:[e.jsxs("div",{ref:C,onMouseMove:I,className:"oe-hero relative hidden lg:flex flex-col justify-center overflow-hidden px-12 xl:px-20 py-14",children:[e.jsx("div",{className:"oe-aurora","aria-hidden":!0,children:e.jsx("div",{className:"oe-aurora-c"})}),e.jsx("div",{className:"oe-spot","aria-hidden":!0}),e.jsxs("div",{className:"oe-font-display relative mb-5 inline-flex w-fit items-center gap-2 rounded-full border border-white/60 bg-white/70 px-3 py-1 text-2xs font-semibold tracking-wider uppercase text-content-secondary backdrop-blur-md dark:border-white/10 dark:bg-white/10 dark:text-white/80",children:[e.jsx("span",{className:"oe-pulse relative flex h-1.5 w-1.5 rounded-full bg-semantic-success"}),e.jsx("span",{children:t("login.welcome_eyebrow","First-time setup")})]}),e.jsxs("h1",{className:"oe-font-display relative max-w-[640px] text-[46px] xl:text-[60px] leading-[0.95] font-semibold tracking-tight text-content-primary dark:text-white",children:[t("login.welcome_h_a","A clean slate,")," ",e.jsxs("span",{className:"relative inline-block",children:[e.jsx("span",{className:"oe-font-serif italic font-normal bg-gradient-to-r from-[#0284c7] via-[#0ea5e9] to-[#38bdf8] bg-clip-text text-transparent",children:t("login.welcome_h_b","ready to build.")}),e.jsx("span",{className:"absolute -inset-x-2 -bottom-1 -z-10 h-[14px] rounded-full bg-gradient-to-r from-[#0284c7]/25 via-[#0ea5e9]/25 to-[#38bdf8]/25 blur-xl"})]})]}),e.jsx("p",{className:"oe-font-display relative mt-5 max-w-[480px] text-base leading-[1.6] text-content-secondary dark:text-white/65",children:t("login.welcome_sub_modules","Sign in to unlock every module - your workspace is empty until you import or create.")}),e.jsx("div",{className:"relative mt-9 grid grid-cols-2 sm:grid-cols-4 xl:grid-cols-5 gap-3 max-w-[680px]",children:U.map((a,s)=>{const n=Ne[a.tone],l=a.icon,i=s%3===0?"oe-tile-float-a":s%3===1?"oe-tile-float-b":"";return e.jsxs("div",{className:`oe-tile oe-font-display ${i} rounded-2xl p-3 animate-stagger-in`,style:{animationDelay:`${80+s*40}ms`},children:[e.jsx("div",{className:`flex h-9 w-9 items-center justify-center rounded-xl ring-1 ${n.bg} ${n.fg} ${n.ring}`,children:e.jsx(l,{size:16,strokeWidth:1.8})}),e.jsx("div",{className:"mt-2.5 text-xs font-semibold leading-tight text-content-primary dark:text-white",children:a.label}),e.jsxs("div",{className:"mt-1 flex items-baseline gap-1.5",children:[e.jsx("span",{className:`text-xl font-semibold tracking-tight leading-none ${a.stat==="—"?"text-content-quaternary/60":"text-content-primary dark:text-white"}`,children:a.stat}),e.jsx("span",{className:"oe-overline",children:a.hint})]})]},a.label)})}),e.jsxs("div",{className:"oe-font-display relative mt-7 flex items-center gap-3 text-2xs font-medium text-content-tertiary",children:[e.jsx("div",{className:"oe-spec-bar h-[2px] w-12 rounded-full"}),e.jsx("span",{children:t("login.workspace_status_first","Empty workspace - sign in to set up your first project")})]}),e.jsxs("div",{className:"relative mt-auto pt-10 text-2xs text-content-tertiary/80 dark:text-white/40",children:["© 2026"," ",e.jsx("a",{href:"https://www.linkedin.com/in/boikoartem/",target:"_blank",rel:"noopener noreferrer",className:"font-medium text-content-secondary hover:text-oe-blue transition-colors dark:text-white/70 dark:hover:text-oe-blue",children:"Artem Boiko"})," ","· OpenConstructionERP · ",e.jsx("a",{href:"mailto:info@datadrivenconstruction.io",className:"hover:text-content-secondary transition-colors",children:"info@datadrivenconstruction.io"})]})]}),e.jsx("div",{className:"flex items-center justify-center px-5 py-10 sm:px-10 relative z-10",children:e.jsx("div",{className:"oe-form-pane w-full max-w-[420px] rounded-[24px]",children:e.jsxs("div",{className:"rounded-[24px] p-7 sm:p-9",children:[e.jsxs("div",{className:"lg:hidden mb-6 flex flex-col items-center",children:[e.jsx(L,{size:"md",animate:!0}),e.jsxs("span",{className:"mt-2.5 text-xl font-medium tracking-tight text-content-primary dark:text-white",style:{fontFamily:"'Plus Jakarta Sans', system-ui, sans-serif"},children:["Open",e.jsx("span",{className:"text-oe-blue",children:"Construction"}),e.jsx("span",{className:"text-content-quaternary",children:"ERP"})]})]}),e.jsxs("div",{className:"hidden lg:flex items-center gap-2 mb-7",children:[e.jsx(L,{size:"sm",animate:!0}),e.jsxs("span",{className:"text-base font-medium tracking-tight text-content-primary dark:text-white",style:{fontFamily:"'Plus Jakarta Sans', system-ui, sans-serif"},children:["Open",e.jsx("span",{className:"text-oe-blue",children:"Construction"}),e.jsx("span",{className:"text-content-quaternary dark:text-white/50",children:"ERP"})]})]}),e.jsxs("div",{className:"animate-stagger-in",style:{animationDelay:"60ms"},children:[e.jsx("h2",{className:"oe-font-display text-[28px] font-semibold tracking-tight text-content-primary dark:text-white",children:t("auth.welcome_back","Welcome back")}),e.jsx("p",{className:"oe-font-display mt-1.5 text-sm text-content-secondary dark:text-white/60",children:t("auth.login_subtitle","Sign in to your workspace")})]}),e.jsxs("form",{onSubmit:G,className:"mt-7 space-y-3 animate-stagger-in",style:{animationDelay:"160ms"},"aria-label":t("auth.login","Sign in"),children:[e.jsx(ue,{id:"login-email-next",name:"email",label:t("auth.email","Email"),type:"email",value:m,onChange:a=>u(a.target.value),placeholder:"you@company.com",autoComplete:"email",required:!0,"aria-required":"true",autoFocus:!0,icon:e.jsx(ge,{size:16})}),e.jsxs("div",{className:"flex flex-col gap-1",children:[e.jsxs("div",{className:"flex items-center justify-between",children:[e.jsx("label",{htmlFor:"login-password-next",className:"text-sm font-medium text-content-primary dark:text-white",children:t("auth.password","Password")}),e.jsx(A,{to:"/forgot-password",className:"text-2xs font-medium text-oe-blue hover:text-oe-blue-hover transition-colors",children:t("auth.forgot_password","Forgot password?")})]}),e.jsxs("div",{className:"relative",children:[e.jsx("div",{className:"pointer-events-none absolute inset-y-0 left-0 flex items-center pl-3 text-content-tertiary",children:e.jsx(xe,{size:16})}),e.jsx("input",{id:"login-password-next",name:"password",type:d?"text":"password",value:j,onChange:a=>g(a.target.value),placeholder:t("auth.password_placeholder","Enter your password"),autoComplete:"current-password",required:!0,"aria-required":"true",minLength:8,className:"oe-input w-full pl-9 pr-9"}),e.jsx("button",{type:"button",onClick:()=>T(!d),"aria-label":d?t("auth.hide_password","Hide password"):t("auth.show_password","Show password"),className:"absolute inset-y-0 right-0 flex items-center pr-3 text-content-tertiary hover:text-content-secondary transition-colors",tabIndex:-1,children:d?e.jsx(pe,{size:16}):e.jsx(he,{size:16})})]})]}),e.jsxs("label",{className:"flex items-center gap-2 cursor-pointer select-none pt-1",children:[e.jsx("input",{type:"checkbox",checked:x,onChange:a=>B(a.target.checked),className:"h-3.5 w-3.5 rounded border-border text-oe-blue focus:ring-oe-blue accent-oe-blue"}),e.jsx("span",{className:"text-xs text-content-secondary dark:text-white/60",children:t("auth.remember_me","Remember me for 30 days")})]}),_&&e.jsxs("div",{className:"flex items-start gap-2 rounded-lg bg-semantic-error-bg px-3 py-2 text-xs text-semantic-error animate-stagger-in",children:[e.jsx("span",{className:"shrink-0 mt-0.5",children:"!"}),e.jsx("span",{children:_})]}),e.jsx(be,{type:"submit",variant:"primary",size:"lg",loading:O,className:"w-full btn-shimmer",children:t("auth.login","Sign in")})]}),$===!0&&e.jsxs("div",{className:"mt-6 animate-stagger-in",style:{animationDelay:"260ms"},children:[e.jsxs("button",{type:"button",onClick:()=>M(!b),className:"flex w-full items-center justify-center gap-2 rounded-xl border border-border-light bg-surface-primary px-4 py-2.5 text-sm text-content-secondary hover:text-oe-blue hover:border-oe-blue/40 transition-all",children:[e.jsx(fe,{size:14,className:"text-oe-blue"}),e.jsx("span",{className:"font-semibold",children:t("auth.demo_access","Demo Access")}),e.jsx(F,{size:14,className:`text-content-tertiary transition-transform duration-200 ${b?"rotate-180":""}`})]}),b&&e.jsx("div",{className:"mt-2 space-y-1.5 animate-stagger-in",children:Y.map(a=>e.jsxs("button",{type:"button",onClick:()=>J(a.email),disabled:S!==null,className:"oe-glass-lite group flex w-full items-center gap-3 rounded-xl px-3.5 py-2.5 text-left transition-all hover:translate-y-[-1px] hover:border-oe-blue/30 disabled:opacity-50",children:[e.jsx("div",{className:`flex h-9 w-9 shrink-0 items-center justify-center rounded-full ${a.color} text-white text-sm font-semibold shadow-sm`,children:S===a.email?e.jsxs("svg",{className:"animate-spin h-4 w-4",viewBox:"0 0 24 24",children:[e.jsx("circle",{className:"opacity-25",cx:"12",cy:"12",r:"10",stroke:"currentColor",strokeWidth:"4",fill:"none"}),e.jsx("path",{className:"opacity-75",fill:"currentColor",d:"M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"})]}):a.letter}),e.jsxs("div",{className:"flex-1 min-w-0",children:[e.jsx("div",{className:"text-sm font-semibold text-content-primary dark:text-white",children:a.name}),e.jsxs("div",{className:"text-2xs text-content-tertiary truncate",children:[a.email," · ",a.role]})]}),e.jsx(ye,{size:16,className:"text-content-quaternary group-hover:text-oe-blue transition-colors shrink-0"})]},a.email))})]}),e.jsx("div",{className:"mt-7 animate-stagger-in",style:{animationDelay:"340ms"},children:e.jsxs("p",{className:"text-center text-xs text-content-secondary dark:text-white/60",children:[t("auth.no_account","Don't have an account?")," ",e.jsx(A,{to:"/register",className:"font-medium text-oe-blue hover:text-oe-blue-hover transition-colors",children:t("auth.create_account","Create account")})]})})]})})})]})]})}export{De as LoginPageNext};
