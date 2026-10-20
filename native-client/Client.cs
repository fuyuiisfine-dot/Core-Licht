using System;
using System.IO;
using System.Linq;
using System.Collections.Generic;
using System.Drawing;
using System.Drawing.Imaging;
using System.Threading.Tasks;
using System.Windows.Forms;

namespace CoreLicht {
class Choice {
    public string Id,Name;public Choice(string id,string name){Id=id;Name=name;}
    public override string ToString(){return Name;}
}
public partial class ClientWindow:Form {
    readonly string folder;
    readonly VoiceAudio voiceAudio;
    readonly bool smoke;
    readonly bool gameplaySmoke;
    readonly int httpPort,tcpPort;
    readonly Dictionary<string,object> resources;
    GameConnection connection;
    List<Dictionary<string,object>> cards=new List<Dictionary<string,object>>();
    Dictionary<string,object> unlocks,selected,team;
    readonly TextBox account=new TextBox(),search=new TextBox();
    readonly Button connect=new Button(),saveSkin=new Button(),saveTeam=new Button();
    readonly Label status=new Label(),title=new Label(),stats=new Label();
    readonly ListView roster=new ListView();
    readonly PictureBox picture=new PictureBox();
    readonly Label missingPortrait=new Label();
    readonly ListBox files=new ListBox(),voices=new ListBox();
    readonly TextBox fileText=new TextBox(),voiceText=new TextBox();
    readonly ComboBox skins=new ComboBox();
    readonly TabControl pages=new TabControl();
    readonly List<ComboBox> slots=new List<ComboBox>();
    readonly System.Windows.Forms.Timer heartbeat=new System.Windows.Forms.Timer();
    int beat;bool rendering;
    Task readTask=Task.FromResult(true);
    static readonly Color Ink=Color.FromArgb(20,26,35),PanelColor=Color.FromArgb(28,36,48),Gold=Color.FromArgb(221,191,126),Light=Color.FromArgb(225,230,238);
    public ClientWindow(string directory,bool testing,bool playtest=false,int httpPort=18080,int tcpPort=19090) {
        folder=directory;this.httpPort=httpPort;this.tcpPort=tcpPort;voiceAudio=new VoiceAudio(folder);smoke=testing||playtest;gameplaySmoke=playtest;resources=Data.Read(Path.Combine(folder,"catalog.json"));
        Text="Core Licht";ClientSize=new Size(1404,648);MinimumSize=new Size(960,480);
        StartPosition=FormStartPosition.CenterScreen;BackColor=Ink;ForeColor=Light;Font=new Font("Microsoft JhengHei UI",10);
        if(smoke){ShowInTaskbar=false;StartPosition=FormStartPosition.Manual;Location=new Point(-20000,-20000);}
        Build();
        heartbeat.Interval=10000;heartbeat.Tick+=async (s,e)=>{if(connection==null)return;try{await connection.Send("1_0",Data.Obj("index",++beat,"client_time",Now(),"server_time",0));}catch(Exception ex){Status("連線已中斷："+ex.Message);heartbeat.Stop();}};
        FormClosed+=(s,e)=>{heartbeat.Stop();voiceAudio.Dispose();if(connection!=null)connection.Dispose();};
        Shown+=async (s,e)=>{if(gameplaySmoke)await RunGameplaySmoke();else if(smoke)await RunSmoke();else await Connect();};
    }
    static long Now(){return (long)(DateTime.UtcNow-new DateTime(1970,1,1)).TotalSeconds;}
    void Status(string text){if(IsDisposed)return;if(InvokeRequired){BeginInvoke(new Action(()=>Status(text)));return;}status.Text=text;if(gameView!=null)gameView.Invalidate();}
    async Task Connect() {
        if(!connect.Enabled||String.IsNullOrWhiteSpace(account.Text))return;connect.Enabled=false;Status("正在連線…");
        try {
            heartbeat.Stop();if(connection!=null){connection.Closed=null;connection.Dispose();}
            connection=new GameConnection(Path.Combine(folder,"protocol"),httpPort,tcpPort);connection.Closed+=message=>Status("連線已中斷；請重新連線。");
            var auth=await connection.Login(account.Text.Trim());var roles=Data.Items(auth["role_list"]);
            if(roles.Count==0)throw new InvalidOperationException("這個本機帳號尚未建立角色。請使用已準備的 windows-preview。");
            var role=Data.Map(roles[0]);selectedRoleId=(int)Data.Number(role["id"]);await connection.Request("1_3",Data.Obj("id",role["id"]));
            cards=Data.Items((await connection.Request("11_1",Data.Obj()))["children_list"]).Select(Data.Map).ToList();
            unlocks=await connection.Request("11_16",Data.Obj());
            var vitality=await connection.Request("13_1",Data.Obj());
            team=Data.Map(Data.Items((await connection.Request("15_4",Data.Obj("event_id","10001")))["children_team"])[0]);
            SetStoryHistory(await connection.Request("26_4",Data.Obj()));
            playerName=Data.Text(role["name"]);playerLevel=Data.Text(role["level"]);energy=Data.Text(vitality["vitality"]);energyMax=Data.Text(vitality["vit_max"]);
            var attributes=connection.Notification("2_2");currency.Clear();if(attributes!=null)foreach(var entry in Data.Items(attributes["kv_list"]).Select(Data.Map))currency[Data.Text(entry["k"])]=Data.Text(entry["v"]);
            Filter();LoadTeam();await GameCommand("state",Data.Obj());heartbeat.Start();Status(String.Format("已連線 · {0} Lv.{1} · {2} 名角色 · 精神力 {3}/{4}",role["name"],role["level"],cards.Count,vitality["vitality"],vitality["vit_max"]));
        }catch(Exception ex){Status("連線失敗："+ex.Message);if(smoke)throw;}finally{connect.Enabled=true;}
    }
    Dictionary<string,object> Catalog(string id){return Data.Map(Data.Map(resources["characters"])[id]);}
    void Filter() {
        roster.BeginUpdate();roster.Items.Clear();
        foreach(var c in cards){var info=Catalog(Data.Text(c["sys_id"]));string name=Data.Text(info["name"]);
            if(search.Text.Length>0&&name.IndexOf(search.Text,StringComparison.OrdinalIgnoreCase)<0)continue;
            var row=new ListViewItem(new[]{name,Data.Text(c["lvl"]),Data.Text(c["favor_lvl"])});row.Tag=c;roster.Items.Add(row);
        }roster.EndUpdate();if(roster.Items.Count>0)SelectCard((Dictionary<string,object>)roster.Items[0].Tag);
    }
    void SelectCard(Dictionary<string,object> card) {
        voiceAudio.Stop();
        rendering=true;selected=card;var info=Catalog(Data.Text(card["sys_id"]));title.Text=Data.Text(info["name"]);
        var attrs=Data.Items(card["attr"]).Select(Data.Map).ToDictionary(a=>Data.Text(a["k"]),a=>Data.Text(a["v"]));
        stats.Text=String.Format("Lv.{0}   星數 {1}   好感 {2}\r\n生命 {3}    攻擊 {4}    防禦 {5}",card["lvl"],card["star"],card["favor_lvl"],Get(attrs,"11"),Get(attrs,"12"),Get(attrs,"14"));
        files.Items.Clear();voices.Items.Clear();skins.Items.Clear();fileText.Clear();voiceText.Clear();
        foreach(var item in Data.Items(info["documents"])) {var d=Data.Map(item);files.Items.Add(new Choice(Data.Text(d["id"]),Data.Text(d["title"])));}
        foreach(var item in Data.Items(info["voices"])) {var d=Data.Map(item);voices.Items.Add(new Choice(Data.Text(d["id"]),Data.Text(d["title"])));}
        foreach(var item in Data.Items(card["skin_list"])) {string id=Data.Text(item);var skin=Data.Map(Data.Map(info["skins"])[id]);skins.Items.Add(new Choice(id,Data.Text(skin["name"])));if(id==Data.Text(card["use_skin"]))skins.SelectedIndex=skins.Items.Count-1;}
        ShowPortrait();rendering=false;if(files.Items.Count>0)files.SelectedIndex=0;if(voices.Items.Count>0)voices.SelectedIndex=0;if(gameView!=null)gameView.Invalidate();
    }
    static string Get(Dictionary<string,string>d,string key){string v;return d.TryGetValue(key,out v)?v:"—";}
    void ShowPortrait() {
        if(picture.Image!=null){picture.Image.Dispose();picture.Image=null;}
        if(selected==null)return;var info=Catalog(Data.Text(selected["sys_id"]));var skin=Data.Map(Data.Map(info["skins"])[Data.Text(selected["use_skin"])]);
        string file=Path.Combine(folder,Data.Text(skin["image"]));
        missingPortrait.Visible=!File.Exists(file);
        if(File.Exists(file)){using(var source=Image.FromFile(file))picture.Image=new Bitmap(source);}
    }
    async Task ReadFile() {
        if(rendering||selected==null||files.SelectedItem==null||unlocks==null)return;
        var choice=(Choice)files.SelectedItem;var entry=Data.Items(unlocks["char_list"]).Select(Data.Map).FirstOrDefault(v=>Data.Text(v["k"])==choice.Id);
        if(entry==null){fileText.Text="這份角色檔案尚未解鎖。";return;}
        var record=Data.Items(Catalog(Data.Text(selected["sys_id"]))["documents"]).Select(Data.Map).First(d=>Data.Text(d["id"])==choice.Id);
        fileText.Text=Data.Text(record["content"]).Replace("\\n","\n").Replace("\r\n","\n").Replace("\n","\r\n");
        if(Data.Number(entry["v"])==0)try{await connection.Request("11_37",Data.Obj("type",1,"sys_id",choice.Id));entry["v"]=1;}catch(Exception ex){Status("已讀狀態尚未保存："+ex.Message);}
    }
    void ReadVoice() {
        voiceAudio.Stop();
        if(rendering||selected==null||voices.SelectedItem==null||unlocks==null)return;
        var choice=(Choice)voices.SelectedItem;bool allowed=Data.Items(unlocks["voice_list"]).Select(Data.Map).Any(v=>Data.Text(v["k"])==choice.Id);
        if(!allowed){voiceText.Text="這段語音尚未解鎖。";return;}
        var record=Data.Items(Catalog(Data.Text(selected["sys_id"]))["voices"]).Select(Data.Map).First(d=>Data.Text(d["id"])==choice.Id);
        voiceText.Text=Data.Text(record["content"])+(voiceAudio.Exists(choice.Id)?"":"\r\n\r\n尚未匯出這段語音的音檔。");
    }
    bool VoiceAllowed() {
        var choice=voices.SelectedItem as Choice;
        return choice!=null&&unlocks!=null&&Data.Items(unlocks["voice_list"]).Select(Data.Map).Any(v=>Data.Text(v["k"])==choice.Id);
    }
    bool VoiceReady() {
        var choice=voices.SelectedItem as Choice;
        return VoiceAllowed()&&choice!=null&&voiceAudio.Exists(choice.Id);
    }
    void ToggleVoice() {
        var choice=voices.SelectedItem as Choice;
        if(choice==null||!VoiceReady())return;
        try {
            if(voiceAudio.PlayingId==choice.Id)voiceAudio.Stop();else voiceAudio.Play(choice.Id);
        }catch(Exception ex){voiceAudio.Stop();Status("語音播放失敗："+ex.Message);}
        if(gameView!=null)gameView.Invalidate();
    }
    async Task ChangeSkin() {
        if(!saveSkin.Enabled||selected==null||skins.SelectedItem==null||connection==null)return;saveSkin.Enabled=false;
        try{var target=(Choice)skins.SelectedItem;await connection.Request("11_20",Data.Obj("id",selected["id"],"skin_id",target.Id));selected["use_skin"]=target.Id;ShowPortrait();Status("造型已保存。");}
        catch(Exception ex){Status("換裝未完成："+ex.Message);}finally{saveSkin.Enabled=true;}
    }
    void LoadTeam() {
        for(int i=0;i<slots.Count;i++){var box=slots[i];box.Items.Clear();box.Items.Add(new Choice("0","空位"));
            foreach(var c in cards)box.Items.Add(new Choice(Data.Text(c["id"]),Data.Text(Catalog(Data.Text(c["sys_id"]))["name"])));
            box.SelectedIndex=0;var entry=Data.Items(team["children_list"]).Select(Data.Map).FirstOrDefault(v=>Data.Number(v["k"])==i+1);
            if(entry!=null)for(int j=1;j<box.Items.Count;j++)if(((Choice)box.Items[j]).Id==Data.Text(entry["v"]))box.SelectedIndex=j;
        }
    }
    async Task SaveTeam() {
        if(!saveTeam.Enabled||connection==null||team==null)return;saveTeam.Enabled=false;
        try{var members=new List<object>();var used=new HashSet<string>();
            for(int i=0;i<slots.Count;i++){var c=slots[i].SelectedItem as Choice;if(c==null||c.Id=="0")continue;if(!used.Add(c.Id))throw new InvalidOperationException("同一角色不能重複編入隊伍。");members.Add(Data.Obj("k",i+1,"v",c.Id));}
            var response=await connection.Request("15_2",Data.Obj("team_index",team["team_index"],"team_id",team["team_id"],"event_id",team["event_id"],"children_list",members,"fetter_child_list",team["fetter_child_list"]));
            team=Data.Map(response["children_team"]);Status("編隊已保存。");
        }catch(Exception ex){Status("編隊未保存："+ex.Message);}finally{saveTeam.Enabled=true;}
    }
    async Task RunSmoke() {
        string result=Path.Combine(folder,"smoke-result.json");
        try{await Connect();if(cards.Count!=75)throw new InvalidDataException("Expected 75 owned characters");
            if(selected==null)SelectCard(cards[0]);await readTask;
            skins.SelectedIndex=skins.Items.Count-1;string wantedSkin=((Choice)skins.SelectedItem).Id;
            await ChangeSkin();
            var checkedCards=Data.Items((await connection.Request("11_1",Data.Obj()))["children_list"]).Select(Data.Map).ToList();
            if(Data.Text(checkedCards[0]["use_skin"])!=wantedSkin)throw new InvalidDataException("Skin was not persisted");
            int first=slots[0].SelectedIndex,second=slots[1].SelectedIndex;slots[0].SelectedIndex=second;slots[1].SelectedIndex=first;
            string wantedMember=((Choice)slots[0].SelectedItem).Id;await SaveTeam();
            var checkedTeam=Data.Map(Data.Items((await connection.Request("15_4",Data.Obj("event_id","10001")))["children_team"])[0]);
            if(Data.Text(Data.Map(Data.Items(checkedTeam["children_list"])[0])["v"])!=wantedMember)throw new InvalidDataException("Team was not persisted");
            await Connect();await readTask;
            if(Data.Text(cards[0]["use_skin"])!=wantedSkin)throw new InvalidDataException("Skin lost after reconnect");
            VerifyGameNavigation();
            bool voiceAudioVerified=VerifyVoiceAudio();
            foreach(string screen in new[]{"Home","Roster","Detail","Files","Skins","Team"}){Navigate(screen);using(var image=new Bitmap(gameView.Width,gameView.Height)){gameView.DrawToBitmap(image,new Rectangle(0,0,image.Width,image.Height));image.Save(Path.Combine(folder,"preview-"+screen.ToLowerInvariant()+".png"),ImageFormat.Png);}}
            Navigate("Home");using(var image=new Bitmap(gameView.Width,gameView.Height)){gameView.DrawToBitmap(image,new Rectangle(0,0,image.Width,image.Height));image.Save(Path.Combine(folder,"preview.png"),ImageFormat.Png);}
            File.WriteAllText(result,Data.Json.Serialize(Data.Obj("success",true,"characters",cards.Count,"files",Data.Items(unlocks["char_list"]).Count,"voices",Data.Items(unlocks["voice_list"]).Count,"voice_audio_verified",voiceAudioVerified,"team_loaded",team!=null,"skin_saved",true,"team_saved",true,"reconnect_verified",true,"native_windows",true,"mobile_navigation_verified",true,"battle_supported",true,"original_combat",false)),System.Text.Encoding.UTF8);
        }catch(Exception ex){File.WriteAllText(result,Data.Json.Serialize(Data.Obj("success",false,"error",ex.ToString())));}
        finally{Close();}
    }
    [STAThread]public static void Main(string[] args) {
        Application.EnableVisualStyles();Application.SetCompatibleTextRenderingDefault(false);
        try{int httpPort=PortArgument(args,"--http-port=",18080),tcpPort=PortArgument(args,"--tcp-port=",19090);Application.Run(new ClientWindow(Path.Combine(AppDomain.CurrentDomain.BaseDirectory,"data"),args.Contains("--smoke-test"),args.Contains("--game-smoke-test"),httpPort,tcpPort));}
        catch(Exception ex){if(args.Contains("--smoke-test")||args.Contains("--game-smoke-test")){File.WriteAllText(Path.Combine(AppDomain.CurrentDomain.BaseDirectory,"startup-error.txt"),ex.ToString());Environment.ExitCode=1;}
            else MessageBox.Show("無法啟動 Windows 預覽版："+ex.Message,"Core Licht",MessageBoxButtons.OK,MessageBoxIcon.Error);}
    }
    static int PortArgument(string[] args,string prefix,int fallback){string value=args.FirstOrDefault(arg=>arg.StartsWith(prefix,StringComparison.Ordinal));if(value==null)return fallback;int port;if(!int.TryParse(value.Substring(prefix.Length),out port)||port<1||port>65535)throw new ArgumentException("Invalid port: "+value);return port;}
}
}
