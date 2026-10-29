/** Browser-only design fixture. All data and agent replies here are fictional. */
import type {Movement, Proposal} from './types';
const categories = ['Nómina y sueldos', 'Pauta Publicitaria', 'Tecnología y software', 'Renta de oficina', 'Investigaciones', 'Comisión de Renta', 'Gasolina', 'Pago de tarjeta', 'Depósito en garantía recibido', 'Por revisar'];
const accounts = [{id: 'efectivo', name: 'Efectivo', kind: 'cash', opening_minor: 680000}, {id: 'banco', name: 'Cuenta bancaria', kind: 'bank', opening_minor: 3200000}, {id: 'tarjeta_bbva', name: 'Tarjeta BBVA', kind: 'credit', opening_minor: -1500000}];
const examples: [string, string, string, number, string, string][] = [
  ['2026-10-28', 'banco', 'Investigaciones', 250000, 'Cobro de investigación · Proyecto Norte', 'operational'],
  ['2026-10-27', 'efectivo', 'Nómina y sueldos', -480000, 'Pago de nómina · Equipo administrativo', 'operational'],
  ['2026-10-25', 'tarjeta_bbva', 'Pauta Publicitaria', -185000, 'Campaña digital · Octubre', 'operational'],
  ['2026-10-23', 'banco', 'Comisión de Renta', 1800000, 'Comisión de renta · Proyecto Jardín', 'operational'],
  ['2026-10-21', 'banco', 'Pago de tarjeta', -300000, 'Pago a tarjeta BBVA', 'card_payment'],
  ['2026-10-21', 'tarjeta_bbva', 'Pago de tarjeta', 300000, 'Pago recibido de cuenta bancaria', 'card_payment'],
  ['2026-10-18', 'tarjeta_bbva', 'Tecnología y software', -125000, 'Herramientas del equipo', 'operational'],
  ['2026-10-16', 'banco', 'Renta de oficina', -650000, 'Renta de oficina · Octubre', 'operational'],
  ['2026-10-14', 'efectivo', 'Comisión de Renta', 920000, 'Comisión de renta · Proyecto Sur', 'operational'],
  ['2026-10-10', 'banco', 'Depósito en garantía recibido', 700000, 'Depósito en garantía · Proyecto Centro', 'custody'],
  ['2026-10-08', 'tarjeta_bbva', 'Gasolina', -68000, 'Visitas de propiedades', 'operational'],
  ['2026-10-04', 'banco', 'Nómina y sueldos', -420000, 'Primera quincena administrativa', 'operational'],
  ['2026-09-20', 'banco', 'Comisión de Renta', 1600000, 'Comisión de renta · Septiembre', 'operational'],
];
let rows: Movement[] = examples.map(([date, account, category, amount_minor, description, treatment], i) => ({id: `demo-${i}`, date, account, kind: account === 'tarjeta_bbva' ? amount_minor < 0 ? 'cargo' : 'pago' : amount_minor < 0 ? 'egreso' : 'ingreso', category, amount_minor, description, treatment, currency: 'MXN', reference: 'Referencia ficticia', property: `DEMO-${String(i + 1).padStart(3, '0')}`, source_file: 'ejemplo-ficticio.xlsx', source_sheet: `Movimientos ${account}`, source_row: i + 4}));
let proposals: Proposal[] = [];
function total(items: Movement[]) {
 const op = items.filter(r => r.treatment === 'operational');
 const income_minor = op.filter(r => r.amount_minor > 0).reduce((n,r) => n+r.amount_minor,0);
 const expense_minor = -op.filter(r => r.amount_minor < 0).reduce((n,r) => n+r.amount_minor,0);
 return {income_minor,expense_minor,operating_net_minor:income_minor-expense_minor,inflow_minor:items.filter(r=>r.amount_minor>0).reduce((n,r)=>n+r.amount_minor,0),outflow_minor:-items.filter(r=>r.amount_minor<0).reduce((n,r)=>n+r.amount_minor,0),count:items.length,excluded_count:items.length-op.length};
}
export async function demoRequest(path: string, options: RequestInit = {}): Promise<unknown> {
 await new Promise(resolve => setTimeout(resolve, 120));
 const url = new URL(path, 'http://demo.local'); const q=url.searchParams;
 let filtered=rows.filter(r=>(!q.get('month')||r.date.startsWith(q.get('month')!))&&(!q.get('account')||r.account===q.get('account'))&&(!q.get('category')||r.category===q.get('category'))&&(!q.get('search')||`${r.description} ${r.category} ${r.property}`.toLowerCase().includes(q.get('search')!.toLowerCase())));
 if(q.has('ids')) filtered=rows.filter(r=>q.get('ids')!.split(',').includes(r.id!));
 if(url.pathname==='/health') return {status:'ok',ai_configured:false,model:'Respuestas simuladas · modo diseño',demo_mode:true};
 if(url.pathname==='/api/meta') return {accounts,categories,months:['2026-10','2026-09'],count:rows.length,pending:proposals.length,local_workbook_available:true};
 if(url.pathname==='/api/proposals'&&!options.method) return proposals.filter(p=>p.status==='pending');
 if(url.pathname==='/api/summary') {
   const cat:Record<string,number>={}, daily:Record<string,{date:string;income_minor:number;expense_minor:number}>={};
   for(const r of filtered.filter(r=>r.treatment==='operational')) {const d=daily[r.date]??={date:r.date,income_minor:0,expense_minor:0}; if(r.amount_minor<0){cat[r.category]=(cat[r.category]||0)-r.amount_minor;d.expense_minor-=r.amount_minor;}else d.income_minor+=r.amount_minor;}
   const a=accounts.filter(a=>!q.get('account')||a.id===q.get('account')).map(a=>({...a,balance_minor:a.opening_minor+rows.filter(r=>r.account===a.id&&(!q.get('month')||r.date.slice(0,7)<=q.get('month')!)).reduce((n,r)=>n+r.amount_minor,0),count:rows.filter(r=>r.account===a.id).length}));
   return {...total(filtered),accounts:a,net_position_minor:a.reduce((n,a)=>n+a.balance_minor,0),categories:Object.entries(cat).map(([name,amount_minor])=>({name,amount_minor})).sort((a,b)=>b.amount_minor-a.amount_minor),daily:Object.values(daily),recent:filtered.slice(0,6),review_count:0,unreconciled_count:filtered.length,month:q.get('month')};
 }
 if(url.pathname==='/api/movements') {const page=Number(q.get('page')||1);return {items:filtered.slice((page-1)*25,page*25),total:filtered.length,page,size:25,totals:total(filtered)};}
 if(url.pathname==='/api/imports/local-preview'||url.pathname==='/api/imports/preview') {const p:Proposal={id:crypto.randomUUID(),kind:'import',status:'pending',created_at:new Date().toISOString(),payload:{filename:'ejemplo-ficticio.xlsx',movements:rows.slice(0,5).map(r=>({...r,id:undefined,duplicate:false})),stats:{total:5,new:5,duplicates:0,errors:0,review:0,accounts:{banco:3,efectivo:1,tarjeta_bbva:1}},errors:[],notes:['Modo diseño: este es un ejemplo ficticio. No se está leyendo el archivo seleccionado.'],openings:[]}};proposals.unshift(p);return p;}
 if(url.pathname==='/api/proposals/manual') {const f=JSON.parse(options.body as string);const negative=['egreso','cargo','interes','comision'].includes(f.kind);const p:Proposal={id:crypto.randomUUID(),kind:'manual',status:'pending',created_at:new Date().toISOString(),payload:{movements:[{...f,amount_minor:negative?-f.amount_minor:f.amount_minor,treatment:'operational',currency:'MXN'}],errors:[],notes:['Datos ficticios · modo diseño'],openings:[]}};proposals.unshift(p);return p;}
 if(url.pathname.startsWith('/api/proposals/')) {const id=url.pathname.split('/')[3];const p=proposals.find(p=>p.id===id);if(!p)throw new Error('Propuesta de ejemplo no encontrada');if(url.pathname.endsWith('/confirm')){if(p.status==='confirmed')return {inserted:0,duplicates:0};rows=[...p.payload.movements.map(r=>({...r,id:crypto.randomUUID()})),...rows];p.status='confirmed';return {inserted:p.payload.movements.length,duplicates:0};}if(url.pathname.endsWith('/reject')){p.status='rejected';return {status:'rejected'};}return p;}
 if(url.pathname==='/api/chat') {const body=JSON.parse(options.body as string);return {message:'Modo diseño: esta es una respuesta simulada para revisar la experiencia del chat. Conecta el backend para consultar los agentes de OpenAI.',evidence:[{filters:{month:body.month,account:body.account,category:null,search:null,operating_only:false},totals:total(rows),movement_ids:rows.map(r=>r.id)}],proposal:null};}
 throw new Error('Esta acción requiere el backend. El modo diseño utiliza únicamente datos ficticios.');
}
