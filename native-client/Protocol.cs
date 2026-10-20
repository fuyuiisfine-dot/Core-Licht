using System;
using System.IO;
using System.Text;
using System.Linq;
using System.Collections;
using System.Collections.Generic;
using System.Globalization;
using System.Threading;
using System.Threading.Tasks;
using System.Net.Sockets;
using System.Net.Http;
using System.Web.Script.Serialization;

namespace CoreLicht {
public static class Data {
    public static readonly JavaScriptSerializer Json=new JavaScriptSerializer {MaxJsonLength=64*1024*1024,RecursionLimit=128};
    public static Dictionary<string,object> Map(object o) {return (Dictionary<string,object>)o;}
    public static List<object> Items(object o) {return o==null?new List<object>():((IEnumerable)o).Cast<object>().ToList();}
    public static string Text(object o) {return Convert.ToString(o,CultureInfo.InvariantCulture);}
    public static long Number(object o) {return Convert.ToInt64(o,CultureInfo.InvariantCulture);}
    public static Dictionary<string,object> Obj(params object[] pairs) {
        var d=new Dictionary<string,object>();for(int i=0;i<pairs.Length;i+=2)d[(string)pairs[i]]=pairs[i+1];return d;
    }
    public static Dictionary<string,object> Read(string path) {return Map(Json.DeserializeObject(File.ReadAllText(path,Encoding.UTF8)));}
}

public class Proto {
    readonly Dictionary<string,Dictionary<string,object>> types=new Dictionary<string,Dictionary<string,object>>();
    readonly Dictionary<string,object> ids;
    public Proto(string folder) {
        ids=Data.Read(Path.Combine(folder,"message_ids.json"));
        foreach(var file in Data.Items(Data.Json.DeserializeObject(File.ReadAllText(Path.Combine(folder,"schemas.json"),Encoding.UTF8)))) {
            var f=Data.Map(file);foreach(var message in Data.Items(f["messages"])) {
                var m=Data.Map(message);types[Data.Text(f["package"])+"."+Data.Text(m["name"])]=m;
            }
        }
    }
    Dictionary<string,object> Type(string direction,string id) {return types[Data.Text(Data.Map(ids[direction])[id])];}
    Dictionary<string,object> Nested(object name) {return types[Data.Text(name).TrimStart('.')];}
    public Dictionary<string,object> New(string direction,string id) {return Defaults(Type(direction,id));}
    Dictionary<string,object> Defaults(Dictionary<string,object> type) {
        var d=new Dictionary<string,object>();
        foreach(var item in Data.Items(type["fields"])) {
            var f=Data.Map(item);if(Data.Text(f["label"])!="LABEL_REQUIRED")continue;
            string t=Data.Text(f["type"]);object value=0;
            if(t=="TYPE_STRING")value="";else if(t=="TYPE_BYTES")value=new byte[0];
            else if(t=="TYPE_MESSAGE")value=Defaults(Nested(f["type_name"]));
            else if(t=="TYPE_BOOL")value=false;
            d[Data.Text(f["name"])]=value;
        }return d;
    }
    public byte[] Encode(string direction,string id,Dictionary<string,object> value) {return EncodeType(Type(direction,id),value);}
    byte[] EncodeType(Dictionary<string,object> type,Dictionary<string,object> values) {
        using(var s=new MemoryStream()) {
            foreach(var item in Data.Items(type["fields"])) {
                var f=Data.Map(item);object value;string name=Data.Text(f["name"]);
                if(!values.TryGetValue(name,out value)) {
                    if(Data.Text(f["label"])=="LABEL_REQUIRED")throw new InvalidDataException("Missing field: "+name);
                    continue;
                }
                var list=Data.Text(f["label"])=="LABEL_REPEATED"?Data.Items(value):new List<object>{value};
                foreach(var v in list)WriteField(s,f,v);
            }return s.ToArray();
        }
    }
    static void Varint(Stream s,ulong n) {while(n>=128){s.WriteByte((byte)((n&127)|128));n>>=7;}s.WriteByte((byte)n);}
    static ulong Unsigned(object v) {
        if(v is string && ((string)v).StartsWith("-"))return unchecked((ulong)long.Parse((string)v,CultureInfo.InvariantCulture));
        if(v is long)return unchecked((ulong)(long)v);
        if(v is int)return unchecked((ulong)(int)v);
        return Convert.ToUInt64(v,CultureInfo.InvariantCulture);
    }
    void WriteField(Stream s,Dictionary<string,object> f,object value) {
        string t=Data.Text(f["type"]);int wire=0;byte[] bytes=null;
        if(t=="TYPE_MESSAGE"){wire=2;bytes=EncodeType(Nested(f["type_name"]),Data.Map(value));}
        else if(t=="TYPE_STRING"){wire=2;bytes=Encoding.UTF8.GetBytes(Data.Text(value));}
        else if(t=="TYPE_BYTES"){wire=2;bytes=value as byte[]??Convert.FromBase64String(Data.Text(value));}
        else if(t=="TYPE_DOUBLE"||t=="TYPE_FIXED64"||t=="TYPE_SFIXED64")wire=1;
        else if(t=="TYPE_FLOAT"||t=="TYPE_FIXED32"||t=="TYPE_SFIXED32")wire=5;
        Varint(s,((ulong)Data.Number(f["number"])<<3)|(uint)wire);
        if(wire==2){Varint(s,(ulong)bytes.Length);s.Write(bytes,0,bytes.Length);}
        else if(wire==1){bytes=t=="TYPE_DOUBLE"?BitConverter.GetBytes(Convert.ToDouble(value)):BitConverter.GetBytes(Unsigned(value));s.Write(bytes,0,8);}
        else if(wire==5){bytes=t=="TYPE_FLOAT"?BitConverter.GetBytes(Convert.ToSingle(value)):BitConverter.GetBytes((uint)Unsigned(value));s.Write(bytes,0,4);}
        else if(t=="TYPE_BOOL")Varint(s,Convert.ToBoolean(value)?1UL:0UL);
        else if(t=="TYPE_SINT32"||t=="TYPE_SINT64"){long n=Data.Number(value);Varint(s,unchecked((ulong)((n<<1)^(n>>63))));}
        else Varint(s,Unsigned(value));
    }
    public Dictionary<string,object> Decode(string direction,string id,byte[] bytes) {
        using(var s=new MemoryStream(bytes))return DecodeType(Type(direction,id),s,bytes.Length,0);
    }
    static ulong ReadVarint(Stream s) {
        ulong result=0;for(int i=0;i<10;i++){int b=s.ReadByte();if(b<0)throw new EndOfStreamException();
            if(i==9&&b>1)throw new InvalidDataException("Oversized varint");result|=(ulong)(b&127)<<(7*i);if((b&128)==0)return result;}
        throw new InvalidDataException("Invalid varint");
    }
    static byte[] Exact(Stream s,int count) {
        if(count<0||count>1024*1024||s.Length-s.Position<count)throw new InvalidDataException("Invalid field length");
        var b=new byte[count];int n=0;while(n<count){int r=s.Read(b,n,count-n);if(r==0)throw new EndOfStreamException();n+=r;}return b;
    }
    Dictionary<string,object> DecodeType(Dictionary<string,object> type,Stream s,long end,int depth) {
        if(depth>64)throw new InvalidDataException("Nested message limit");
        var fields=Data.Items(type["fields"]).Select(Data.Map).ToDictionary(f=>(int)Data.Number(f["number"]));
        var result=new Dictionary<string,object>();
        foreach(var f in fields.Values)if(Data.Text(f["label"])=="LABEL_REPEATED")result[Data.Text(f["name"])]=new List<object>();
        while(s.Position<end) {
            ulong tag=ReadVarint(s);int wire=(int)(tag&7),num=(int)(tag>>3);Dictionary<string,object> f;
            if(num==0)throw new InvalidDataException("Invalid field number");
            bool known=fields.TryGetValue(num,out f);string t=known?Data.Text(f["type"]):"";object value;
            if(wire==0){ulong n=ReadVarint(s);value=n;
                if(t=="TYPE_SINT32"||t=="TYPE_SINT64")value=unchecked((long)(n>>1)^-((long)n&1));
                else if(t=="TYPE_INT32")value=unchecked((int)n);else if(t=="TYPE_INT64")value=unchecked((long)n);
                else if(t=="TYPE_BOOL")value=n!=0;
            }else if(wire==1){var b=Exact(s,8);value=t=="TYPE_DOUBLE"?(object)BitConverter.ToDouble(b,0):BitConverter.ToUInt64(b,0);}
            else if(wire==5){var b=Exact(s,4);value=t=="TYPE_FLOAT"?(object)BitConverter.ToSingle(b,0):BitConverter.ToUInt32(b,0);}
            else if(wire==2){int len=checked((int)ReadVarint(s));var b=Exact(s,len);
                if(t=="TYPE_MESSAGE"){using(var nested=new MemoryStream(b))value=DecodeType(Nested(f["type_name"]),nested,len,depth+1);}
                else if(t=="TYPE_STRING")value=new UTF8Encoding(false,true).GetString(b);
                else if(known&&Data.Text(f["label"])=="LABEL_REPEATED"&&t!="TYPE_BYTES") {
                    using(var packed=new MemoryStream(b)){var values=(List<object>)result[Data.Text(f["name"])];
                        while(packed.Position<packed.Length)values.Add(ReadVarint(packed));}continue;
                }else value=b;
            }else throw new InvalidDataException("Unsupported wire type");
            if(!known)continue;string name=Data.Text(f["name"]);
            if(Data.Text(f["label"])=="LABEL_REPEATED")((List<object>)result[name]).Add(value);else result[name]=value;
        }
        if(s.Position!=end)throw new InvalidDataException("Message boundary mismatch");
        foreach(var f in fields.Values)if(Data.Text(f["label"])=="LABEL_REQUIRED"&&!result.ContainsKey(Data.Text(f["name"])))throw new InvalidDataException("Missing required field");
        return result;
    }
}

public class GameConnection:IDisposable {
    public readonly Proto Protocol;
    readonly byte[] xor;
    readonly int httpPort,tcpPort;
    TcpClient socket;NetworkStream stream;
    readonly SemaphoreSlim writer=new SemaphoreSlim(1);
    readonly Dictionary<string,TaskCompletionSource<Dictionary<string,object>>> pending=new Dictionary<string,TaskCompletionSource<Dictionary<string,object>>>();
    readonly Dictionary<string,Dictionary<string,object>> notifications=new Dictionary<string,Dictionary<string,object>>();
    public Dictionary<string,object> Notification(string id){lock(notifications){Dictionary<string,object> value;return notifications.TryGetValue(id,out value)?value:null;}}
    ushort unique=100;
    Dictionary<string,object> localCredentials;
    public Action<string> Closed;
    public GameConnection(string folder,int httpPort=18080,int tcpPort=19090){this.httpPort=httpPort;this.tcpPort=tcpPort;Protocol=new Proto(folder);xor=File.ReadAllBytes(Path.Combine(folder,"packet_xor_table.bin"));if(xor.Length!=256)throw new InvalidDataException("Invalid protocol table");}
    public async Task<Dictionary<string,object>> Login(string uid) {
        Dictionary<string,object> creds;
        using(var handler=new HttpClientHandler{AllowAutoRedirect=false})using(var http=new HttpClient(handler)) {
            http.Timeout=TimeSpan.FromSeconds(10);
            var reply=await http.PostAsync("http://127.0.0.1:"+httpPort+"/local/login",new StringContent(Data.Json.Serialize(Data.Obj("uid",uid)),Encoding.UTF8,"application/json"));
            reply.EnsureSuccessStatusCode();creds=Data.Map(Data.Map(Data.Json.DeserializeObject(await reply.Content.ReadAsStringAsync()))["data"]);
        }
        localCredentials=creds;
        socket=new TcpClient();await socket.ConnectAsync("127.0.0.1",tcpPort);stream=socket.GetStream();
        await stream.WriteAsync(new byte[]{1,2},0,2);
        Task receiver=Receive();
        var auth=Protocol.New("c2s","1_1");foreach(string k in new[]{"uid","uname","p_key","token","time"})auth[k]=creds[k];
        if(auth.ContainsKey("game_version"))auth["game_version"]="windows-preview-0.1";
        return await Request("1_1",auth);
    }
    public async Task Send(string id,Dictionary<string,object> value) {
        byte[] payload=Protocol.Encode("c2s",id,value);var parts=id.Split('_');
        await writer.WaitAsync();try{
            ushort seq=unique++;int len=4+payload.Length;if(len>65535)throw new InvalidDataException("Packet too large");
            byte[] packet=new byte[len+2];packet[0]=(byte)(len>>8);packet[1]=(byte)len;packet[2]=(byte)(seq>>8);packet[3]=(byte)seq;packet[4]=byte.Parse(parts[0]);packet[5]=byte.Parse(parts[1]);
            for(int i=0;i<payload.Length;i++)packet[i+6]=(byte)(payload[i]^xor[(seq+i)&255]);
            await stream.WriteAsync(packet,0,packet.Length);
        }finally{writer.Release();}
    }
    public async Task<Dictionary<string,object>> Gameplay(string command,int role,Dictionary<string,object> arguments){
        if(localCredentials==null)throw new InvalidOperationException("請先登入。");
        var body=new Dictionary<string,object>(arguments);body["role_id"]=role;
        foreach(string k in new[]{"uid","token","p_key"})body[k]=localCredentials[k];
        using(var handler=new HttpClientHandler{AllowAutoRedirect=false,UseProxy=false})using(var http=new HttpClient(handler)){
            http.Timeout=TimeSpan.FromSeconds(10);
            var reply=await http.PostAsync("http://127.0.0.1:"+httpPort+"/local/game/"+command,new StringContent(Data.Json.Serialize(body),Encoding.UTF8,"application/json"));
            var value=Data.Map(Data.Json.DeserializeObject(await reply.Content.ReadAsStringAsync()));
            if(!reply.IsSuccessStatusCode)throw new InvalidOperationException(value.ContainsKey("error")?Data.Text(value["error"]):"遊戲服務沒有回應。");
            return Data.Map(value["data"]);
        }
    }
    public async Task<Dictionary<string,object>> Request(string id,Dictionary<string,object> values) {
        var waiter=new TaskCompletionSource<Dictionary<string,object>>();
        lock(pending){if(pending.ContainsKey(id))throw new InvalidOperationException("Request already pending");pending[id]=waiter;}
        try {await Send(id,values);if(await Task.WhenAny(waiter.Task,Task.Delay(15000))!=waiter.Task)throw new TimeoutException("Server has not completed request "+id);return await waiter.Task;}
        finally{lock(pending)pending.Remove(id);}
    }
    async Task<byte[]> Read(int count) {
        byte[] b=new byte[count];int n=0;while(n<count){int r=await stream.ReadAsync(b,n,count-n);if(r==0)throw new EndOfStreamException();n+=r;}return b;
    }
    async Task Receive() {
        try{while(true){var prefix=await Read(2);int length=(prefix[0]<<8)|prefix[1];if(length<3)throw new InvalidDataException("Invalid frame");var b=await Read(length);
            if(b[2]!=0)throw new NotSupportedException("Compressed server packets are not enabled in this preview");
            string id=b[0]+"_"+b[1];byte[] payload=new byte[length-3];int start=(b[0]<<4)+b[1];
            for(int i=0;i<payload.Length;i++)payload[i]=(byte)(b[i+3]^xor[(start+i)&255]);
            var message=Protocol.Decode("s2c",id,payload);TaskCompletionSource<Dictionary<string,object>> waiter;
            if(id=="2_2")lock(notifications)notifications[id]=message;
            lock(pending){if(pending.TryGetValue(id,out waiter))waiter.TrySetResult(message);}
        }}catch(Exception ex){lock(pending){foreach(var w in pending.Values)w.TrySetException(ex);}if(Closed!=null)Closed(ex.Message);}
    }
    public void Dispose(){if(socket!=null)socket.Close();}
}
}
