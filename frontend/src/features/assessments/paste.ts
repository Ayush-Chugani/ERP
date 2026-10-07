export function parseMarkPaste(text:string,roster:{course_registration_id:string;student_number:string}[]){
 if(text.length>100000)throw new Error('Paste is limited to 100 KB.');
 const lines=text.trim().split(/\r?\n/);if(lines.length>500)throw new Error('Paste at most 500 rows.');
 const seen=new Set<string>();
 return lines.map((line,index)=>{const [student,status,raw='',remarks='',...extra]=line.split('\t').map(s=>s.trim());
  const match=roster.find(r=>r.student_number===student);if(!match||seen.has(student)||extra.length)throw new Error('Unknown/duplicate student or extra columns at row '+(index+1));seen.add(student);
  if(!['PRESENT','ABSENT','EXEMPTED','MALPRACTICE'].includes(status))throw new Error('Invalid attendance at row '+(index+1));
  if(status==='PRESENT'&&!/^\d+(\.\d{1,2})?$/.test(raw))throw new Error('Use a nonnegative decimal mark at row '+(index+1));
  if(status!=='PRESENT'&&raw)throw new Error('Leave special-status marks empty.');
  if(remarks.length>500||/^[=+@-]/.test(remarks))throw new Error('Remove formula-like or oversized remarks.');
  return {course_registration_id:match.course_registration_id,attendance_status:status,marks_obtained:raw||null,remarks};
 });
}
