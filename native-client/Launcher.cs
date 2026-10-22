using System;
using System.Diagnostics;
using System.IO;
using System.Net;
using System.Net.Sockets;
using System.Threading;
using System.Windows.Forms;
using System.Web.Script.Serialization;
using System.Collections.Generic;

class Launcher {
    static bool Ready() {
        try {
            var request=(HttpWebRequest)WebRequest.Create("http://127.0.0.1:18080/health");
            request.Proxy=null;request.Timeout=1000;
            using(var response=request.GetResponse())using(var reader=new StreamReader(response.GetResponseStream())) {
                var value=new JavaScriptSerializer().Deserialize<Dictionary<string,object>>(reader.ReadToEnd());
                return value.ContainsKey("status") && Convert.ToString(value["status"])=="prototype";
            }
        }catch{return false;}
    }
    [STAThread] static void Main(string[] args) {
        try {
            string root=AppDomain.CurrentDomain.BaseDirectory;
            if(!Ready()) {
                foreach(int port in new[]{18080,19090})using(var socket=new TcpClient()) {
                    try{socket.Connect("127.0.0.1",port);}catch(SocketException){continue;}
                    throw new IOException("Port "+port+" is occupied. Close the conflicting service and try again.");
                }
                string saves=Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData),"CoreLicht","server-data");
                Directory.CreateDirectory(saves);
                var start=new ProcessStartInfo(Path.Combine(root,"server","CoreLichtServer.exe"),"--listen-host 127.0.0.1 --database \""+Path.Combine(saves,"server.sqlite3")+"\"");
                start.UseShellExecute=false;start.CreateNoWindow=true;start.WindowStyle=ProcessWindowStyle.Hidden;start.WorkingDirectory=root;
                Process.Start(start);
                bool ready=false;for(int i=0;i<60;i++){if(Ready()){ready=true;break;}Thread.Sleep(500);}
                if(!ready)throw new IOException("Local server startup timed out. Save directory: "+saves);
            }
            if(Array.IndexOf(args,"--check")>=0)return;
            var client=new ProcessStartInfo(Path.Combine(root,"CoreLicht.exe"));client.WorkingDirectory=root;Process.Start(client);
        }catch(Exception ex){
            if(Array.IndexOf(args,"--check")>=0){Console.Error.WriteLine(ex.Message);Environment.ExitCode=1;}
            else MessageBox.Show(ex.Message,"Core Licht",MessageBoxButtons.OK,MessageBoxIcon.Error);
        }
    }
}
