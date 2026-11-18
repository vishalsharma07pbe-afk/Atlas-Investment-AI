
type Exchange=""|"NSE"|"BSE";

export default function ExchangePicker({value,onChange,label="Exchange"}:{value:string;onChange:(value:Exchange)=>void;label?:string}){
  const options:{value:Exchange;label:string;hint:string}[]=[
    {value:"",label:"All",hint:"NSE and BSE"},
    {value:"NSE",label:"NSE",hint:"National Stock Exchange"},
    {value:"BSE",label:"BSE",hint:"Bombay Stock Exchange"}
  ];
  return <div className="exchange-picker" role="group" aria-label={label}>
    {options.map(option=><button key={option.label} type="button" className={value===option.value?"selected":""} aria-pressed={value===option.value} title={option.hint} onClick={()=>onChange(option.value)}>{option.label}</button>)}
  </div>;
}
