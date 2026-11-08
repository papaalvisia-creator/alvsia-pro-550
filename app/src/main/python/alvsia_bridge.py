import os,re
def _authorized():
 try:
  from com.alvsia.pro.sec import SessionGate
  return bool(SessionGate.isSessionAuthorized())
 except:return False
def _isr():
 try:
  import pkgutil,sealed_loader
  if os.environ.get("ALVSIA_SEALED_RUNTIME")=="1" and pkgutil.get_data("sealed","alvsia_bridge_impl.alv"):sealed_loader.install()
 except:pass
_CD=""
def configure_diagnostic():return _CD
def _extract_str(v):
 try:return v if isinstance(v,str) else str(v.toString())
 except:return str(v)
def _bin(k,v):
 try:
  p=os.path.realpath(_extract_str(v).strip())
  if not os.path.isfile(p) or not os.access(p,os.X_OK):raise ValueError()
  os.environ[k]=p;return True
 except:os.environ.pop(k,None);return False
def configure_unluac_rs(v):return _bin("ALVSIA_UNLUAC_RS_BIN",v)
def configure_luau_decompiler(v):return _bin("ALVSIA_LUAU_DECOMPILER_BIN",v)
def configure_runtime(token,sealed_runtime="1"):
 global _CD
 try:
  token=_extract_str(token).strip()
  if not re.fullmatch(r"[0-9A-Fa-f]{64}",token):_CD="error";return False
  from com.alvsia.pro.sec import SessionGate
  if not bool(SessionGate.isTokenCurrent(token)):_CD="error";return False
  os.environ.pop("ALVSIA_SESSION_TOKEN",None);os.environ["ALVSIA_APK_SESSION"]="1"
  os.environ["ALVSIA_SEALED_RUNTIME"]="1" if str(sealed_runtime).strip()=="1" else "0"
  _isr();_CD="ok";return True
 except:_CD="error";return False
def run_tool(m,s,i,o,e,j):
 if not _authorized() or os.environ.get("ALVSIA_APK_SESSION")!="1":return "X AUTH: login required"
 _isr()
 try:
  import alvsia_bridge_impl as impl
  result=impl.run_tool(m,s,i,o,e,j)
  try:
   from alvsia_features import scrub_foreign_branding,scrub_output_text_files
   result,_=scrub_foreign_branding(result);scrub_output_text_files(o)
  except:pass
  return result
 except:return "X SEALED BRIDGE: operation failed"
def bridge_run_sub(m,s,i,en,w,j):return run_tool(int(m),str(s),str(i) if i else "",str(w),str(j),str(j))
