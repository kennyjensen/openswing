// A single-page PDF containing the captured RGB JPEG, with its aspect ratio
// and pixels retained. All PDF syntax is ASCII; offsets count binary bytes.
export function aircraftPDF(jpeg,width,height){
  if(!(jpeg instanceof Uint8Array)||jpeg[0]!==255||jpeg[1]!==216)throw new Error('The aircraft image could not be encoded as JPEG.');
  if(!Number.isInteger(width)||!Number.isInteger(height)||width<1||height<1)throw new Error('Invalid aircraft image size.');
  const chunks=[],offsets=[0];let length=0;
  const append=value=>{const bytes=typeof value==='string'?Uint8Array.from(value,c=>c.charCodeAt(0)):value;chunks.push(bytes);length+=bytes.length;};
  const object=(id,parts)=>{offsets[id]=length;append(`${id} 0 obj\n`);for(const part of parts)append(part);append('\nendobj\n');};
  const w=width*.75,h=height*.75;
  append('%PDF-1.4\n%\xe2\xe3\xcf\xd3\n');
  object(1,['<< /Type /Catalog /Pages 2 0 R >>']);
  object(2,['<< /Type /Pages /Kids [3 0 R] /Count 1 >>']);
  object(3,[`<< /Type /Page /Parent 2 0 R /MediaBox [0 0 ${w} ${h}] /Resources << /XObject << /Im0 4 0 R >> >> /Contents 5 0 R >>`]);
  object(4,[`<< /Type /XObject /Subtype /Image /Width ${width} /Height ${height} /ColorSpace /DeviceRGB /BitsPerComponent 8 /Filter /DCTDecode /Length ${jpeg.length} >>\nstream\n`,jpeg,'\nendstream']);
  const draw=`q\n${w} 0 0 ${h} 0 0 cm\n/Im0 Do\nQ\n`;
  object(5,[`<< /Length ${draw.length} >>\nstream\n${draw}endstream`]);
  const xref=length;
  append('xref\n0 6\n0000000000 65535 f \n');
  for(const offset of offsets.slice(1))append(`${String(offset).padStart(10,'0')} 00000 n \n`);
  append(`trailer\n<< /Size 6 /Root 1 0 R >>\nstartxref\n${xref}\n%%EOF\n`);
  const result=new Uint8Array(length);let cursor=0;
  for(const chunk of chunks){result.set(chunk,cursor);cursor+=chunk.length;}
  return result;
}
