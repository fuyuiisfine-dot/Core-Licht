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
public class ClientWindow:Form {
    readonly string folder;
    readonly bool smoke;
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
    public ClientWindow(string directory,bool testing) {
        folder=directory;smoke=testing;resources=Data.Read(Path.Combine(folder,"catalog.json"));
        Text="Core Licht — Windows 開發預覽";Size=new Size(1320,880);MinimumSize=new Size(1100,760);
        StartPosition=FormStartPosition.CenterScreen;BackColor=Ink;ForeColor=Light;Font=new Font("Microsoft JhengHei UI",10);
        if(smoke){ShowInTaskbar=false;StartPosition=FormStartPosition.Manual;Location=new Point(-20000,-20000);}
        Build();
        heartbeat.Interval=10000;heartbeat.Tick+=async (s,e)=>{if(connection==null)return;try{await connection.Send("1_0",Data.Obj("index",++beat,"client_time",Now(),"server_time",0));}catch(Exception ex){Status("連線已中斷："+ex.Message);heartbeat.Stop();}};
        FormClosed+=(s,e)=>{heartbeat.Stop();if(connection!=null)connection.Dispose();};
        Shown+=async (s,e)=>{if(smoke)await RunSmoke();else await Connect();};
    }
    static long Now(){return (long)(DateTime.UtcNow-new DateTime(1970,1,1)).TotalSeconds;}
    static void Fill(Control c){c.Dock=DockStyle.Fill;}
    static void Box(TextBox t){t.Multiline=true;t.ReadOnly=true;t.ScrollBars=ScrollBars.Vertical;t.BackColor=PanelColor;t.ForeColor=Light;t.BorderStyle=BorderStyle.None;t.Font=new Font("Microsoft JhengHei UI",11);}
    static Button ButtonText(string text){return new Button{Text=text,AutoSize=true,FlatStyle=FlatStyle.Flat,BackColor=PanelColor,ForeColor=Gold,Padding=new Padding(10,4,10,4)};}
    void Build() {
        var layout=new TableLayoutPanel{Dock=DockStyle.Fill,Padding=new Padding(20),ColumnCount=1,RowCount=3};
        layout.RowStyles.Add(new RowStyle(SizeType.Absolute,68));layout.RowStyles.Add(new RowStyle(SizeType.Percent,100));layout.RowStyles.Add(new RowStyle(SizeType.Absolute,38));Controls.Add(layout);
        var header=new FlowLayoutPanel{Dock=DockStyle.Fill,WrapContents=false};
        header.Controls.Add(new Label{Text="CORE LICHT",ForeColor=Gold,Font=new Font("Segoe UI",20,FontStyle.Bold),AutoSize=true,Margin=new Padding(0,5,35,0)});
        header.Controls.Add(new Label{Text="本機帳號",AutoSize=true,Margin=new Padding(0,14,10,0)});
        account.Text="windows-preview";account.ForeColor=Ink;account.Width=180;account.Margin=new Padding(0,10,16,0);header.Controls.Add(account);
        connect.Text="連線 / 重新整理";connect.Width=155;connect.Height=38;connect.BackColor=Gold;connect.ForeColor=Ink;connect.FlatStyle=FlatStyle.Flat;connect.Margin=new Padding(0,7,20,0);connect.Click+=async(s,e)=>await Connect();header.Controls.Add(connect);
        header.Controls.Add(new Label{Text="Windows 原生預覽 · 戰鬥尚未開放",AutoSize=true,ForeColor=Color.FromArgb(149,166,187),Margin=new Padding(0,14,0,0)});layout.Controls.Add(header,0,0);
        var body=new TableLayoutPanel{Dock=DockStyle.Fill,ColumnCount=3,RowCount=1};body.ColumnStyles.Add(new ColumnStyle(SizeType.Absolute,315));body.ColumnStyles.Add(new ColumnStyle(SizeType.Percent,43));body.ColumnStyles.Add(new ColumnStyle(SizeType.Percent,57));layout.Controls.Add(body,0,1);
        var left=new TableLayoutPanel{Dock=DockStyle.Fill,ColumnCount=1,RowCount=2,Padding=new Padding(0,0,12,0)};left.RowStyles.Add(new RowStyle(SizeType.Absolute,42));left.RowStyles.Add(new RowStyle(SizeType.Percent,100));
        search.Dock=DockStyle.Top;search.TextChanged+=(s,e)=>Filter();search.BackColor=PanelColor;search.ForeColor=Light;left.Controls.Add(search,0,0);
        roster.Dock=DockStyle.Fill;roster.View=View.Details;roster.FullRowSelect=true;roster.MultiSelect=false;roster.HideSelection=false;roster.BackColor=PanelColor;roster.ForeColor=Light;roster.BorderStyle=BorderStyle.None;roster.Columns.Add("適格體",130);roster.Columns.Add("等級",58);roster.Columns.Add("好感",57);
        roster.SelectedIndexChanged+=(s,e)=>{if(roster.SelectedItems.Count>0)SelectCard((Dictionary<string,object>)roster.SelectedItems[0].Tag);};left.Controls.Add(roster,0,1);body.Controls.Add(left,0,0);
        roster.OwnerDraw=true;
        roster.DrawColumnHeader+=(s,e)=>{using(var brush=new SolidBrush(PanelColor))e.Graphics.FillRectangle(brush,e.Bounds);TextRenderer.DrawText(e.Graphics,e.Header.Text,Font,e.Bounds,Gold,TextFormatFlags.Left|TextFormatFlags.VerticalCenter);};
        roster.DrawItem+=(s,e)=>{};
        roster.DrawSubItem+=(s,e)=>{bool active=e.Item.Selected;using(var brush=new SolidBrush(active?Color.FromArgb(79,67,43):PanelColor))e.Graphics.FillRectangle(brush,e.Bounds);TextRenderer.DrawText(e.Graphics,e.SubItem.Text,Font,e.Bounds,active?Gold:Light,TextFormatFlags.Left|TextFormatFlags.VerticalCenter);};
        var art=new Panel{Dock=DockStyle.Fill,Padding=new Padding(8),BackColor=Color.FromArgb(23,31,43)};picture.Dock=DockStyle.Fill;picture.SizeMode=PictureBoxSizeMode.Zoom;picture.BackColor=art.BackColor;art.Controls.Add(picture);
        missingPortrait.Text="這套造型的立繪尚未取得";missingPortrait.Dock=DockStyle.Fill;missingPortrait.TextAlign=ContentAlignment.MiddleCenter;missingPortrait.Visible=false;art.Controls.Add(missingPortrait);missingPortrait.BringToFront();body.Controls.Add(art,1,0);
        var right=new TableLayoutPanel{Dock=DockStyle.Fill,Padding=new Padding(20,0,0,0),ColumnCount=1,RowCount=3};right.RowStyles.Add(new RowStyle(SizeType.Absolute,56));right.RowStyles.Add(new RowStyle(SizeType.Absolute,92));right.RowStyles.Add(new RowStyle(SizeType.Percent,100));
        title.Text="請連線至本機 server";title.ForeColor=Gold;title.Font=new Font("Microsoft JhengHei UI",22,FontStyle.Bold);title.Dock=DockStyle.Fill;right.Controls.Add(title,0,0);
        stats.Dock=DockStyle.Fill;stats.Text="角色、好感度、造型與編隊會從 server 載入。";right.Controls.Add(stats,0,1);
        pages.Dock=DockStyle.Fill;right.Controls.Add(pages,0,2);body.Controls.Add(right,2,0);
        var documents=new TabPage("角色檔案");var docLayout=SplitText(files,fileText);documents.Controls.Add(docLayout);pages.TabPages.Add(documents);files.SelectedIndexChanged+=(s,e)=>{readTask=ReadFile();};
        var audio=new TabPage("語音台詞");audio.Controls.Add(SplitText(voices,voiceText));pages.TabPages.Add(audio);voices.SelectedIndexChanged+=(s,e)=>ReadVoice();
        var style=new TabPage("造型");style.BackColor=PanelColor;skins.DropDownStyle=ComboBoxStyle.DropDownList;skins.Dock=DockStyle.Top;skins.Height=34;style.Controls.Add(skins);saveSkin.Text="穿戴造型";saveSkin.Dock=DockStyle.Bottom;saveSkin.Height=42;saveSkin.Click+=async(s,e)=>await ChangeSkin();style.Controls.Add(saveSkin);pages.TabPages.Add(style);
        var teamPage=new TabPage("編隊");teamPage.BackColor=PanelColor;var teamLayout=new TableLayoutPanel{Dock=DockStyle.Fill,ColumnCount=1,RowCount=10,Padding=new Padding(12)};
        teamLayout.Controls.Add(new Label{Text="一般作戰隊伍 · 8 個位置",AutoSize=true},0,0);
        for(int i=0;i<8;i++){var slot=new ComboBox{Dock=DockStyle.Top,DropDownStyle=ComboBoxStyle.DropDownList};slots.Add(slot);teamLayout.Controls.Add(slot,0,i+1);}
        saveTeam.Text="保存編隊";saveTeam.Dock=DockStyle.Top;saveTeam.Height=42;saveTeam.Click+=async(s,e)=>await SaveTeam();teamLayout.Controls.Add(saveTeam,0,9);teamPage.Controls.Add(teamLayout);pages.TabPages.Add(teamPage);
        status.Dock=DockStyle.Fill;status.ForeColor=Color.FromArgb(153,175,196);status.Text="尚未連線 · 127.0.0.1";status.TextAlign=ContentAlignment.MiddleLeft;layout.Controls.Add(status,0,2);
    }
    Control SplitText(ListBox list,TextBox text) {
        var p=new TableLayoutPanel{Dock=DockStyle.Fill,RowCount=2,ColumnCount=1,Padding=new Padding(12),BackColor=PanelColor};p.RowStyles.Add(new RowStyle(SizeType.Absolute,140));p.RowStyles.Add(new RowStyle(SizeType.Percent,100));
        list.Dock=DockStyle.Fill;list.BackColor=PanelColor;list.ForeColor=Gold;list.BorderStyle=BorderStyle.None;p.Controls.Add(list,0,0);Box(text);Fill(text);p.Controls.Add(text,0,1);return p;
    }
    void Status(string text){if(IsDisposed)return;if(InvokeRequired){BeginInvoke(new Action(()=>Status(text)));return;}status.Text=text;}
    async Task Connect() {
        if(String.IsNullOrWhiteSpace(account.Text))return;connect.Enabled=false;Status("正在連線…");
        try {
            heartbeat.Stop();if(connection!=null){connection.Closed=null;connection.Dispose();}
            connection=new GameConnection(Path.Combine(folder,"protocol"));connection.Closed+=message=>Status("連線已中斷；請重新連線。");
            var auth=await connection.Login(account.Text.Trim());var roles=Data.Items(auth["role_list"]);
            if(roles.Count==0)throw new InvalidOperationException("這個本機帳號尚未建立角色。請使用已準備的 windows-preview。");
            var role=Data.Map(roles[0]);await connection.Request("1_3",Data.Obj("id",role["id"]));
            cards=Data.Items((await connection.Request("11_1",Data.Obj()))["children_list"]).Select(Data.Map).ToList();
            unlocks=await connection.Request("11_16",Data.Obj());
            var vitality=await connection.Request("13_1",Data.Obj());
            team=Data.Map(Data.Items((await connection.Request("15_4",Data.Obj("event_id","10001")))["children_team"])[0]);
            Filter();LoadTeam();heartbeat.Start();Status(String.Format("已連線 · {0} Lv.{1} · {2} 名角色 · 精神力 {3}/{4}",role["name"],role["level"],cards.Count,vitality["vitality"],vitality["vit_max"]));
        }catch(Exception ex){Status("連線失敗："+ex.Message);if(smoke)throw;}finally{connect.Enabled=true;}
    }
    Dictionary<string,object> Catalog(string id){return Data.Map(Data.Map(resources["characters"])[id]);}
    void Filter() {
        roster.BeginUpdate();roster.Items.Clear();
        foreach(var c in cards){var info=Catalog(Data.Text(c["sys_id"]));string name=Data.Text(info["name"]);
            if(search.Text.Length>0&&name.IndexOf(search.Text,StringComparison.OrdinalIgnoreCase)<0)continue;
            var row=new ListViewItem(new[]{name,Data.Text(c["lvl"]),Data.Text(c["favor_lvl"])});row.Tag=c;roster.Items.Add(row);
        }roster.EndUpdate();if(roster.Items.Count>0){roster.Items[0].Selected=true;roster.Select();}
    }
    void SelectCard(Dictionary<string,object> card) {
        rendering=true;selected=card;var info=Catalog(Data.Text(card["sys_id"]));title.Text=Data.Text(info["name"]);
        var attrs=Data.Items(card["attr"]).Select(Data.Map).ToDictionary(a=>Data.Text(a["k"]),a=>Data.Text(a["v"]));
        stats.Text=String.Format("Lv.{0}   星數 {1}   好感 {2}\r\n生命 {3}    攻擊 {4}    防禦 {5}",card["lvl"],card["star"],card["favor_lvl"],Get(attrs,"11"),Get(attrs,"12"),Get(attrs,"14"));
        files.Items.Clear();voices.Items.Clear();skins.Items.Clear();fileText.Clear();voiceText.Clear();
        foreach(var item in Data.Items(info["documents"])) {var d=Data.Map(item);files.Items.Add(new Choice(Data.Text(d["id"]),Data.Text(d["title"])));}
        foreach(var item in Data.Items(info["voices"])) {var d=Data.Map(item);voices.Items.Add(new Choice(Data.Text(d["id"]),Data.Text(d["title"])));}
        foreach(var item in Data.Items(card["skin_list"])) {string id=Data.Text(item);var skin=Data.Map(Data.Map(info["skins"])[id]);skins.Items.Add(new Choice(id,Data.Text(skin["name"])));if(id==Data.Text(card["use_skin"]))skins.SelectedIndex=skins.Items.Count-1;}
        ShowPortrait();rendering=false;if(files.Items.Count>0)files.SelectedIndex=0;if(voices.Items.Count>0)voices.SelectedIndex=0;
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
        if(rendering||selected==null||voices.SelectedItem==null||unlocks==null)return;
        var choice=(Choice)voices.SelectedItem;bool allowed=Data.Items(unlocks["voice_list"]).Select(Data.Map).Any(v=>Data.Text(v["k"])==choice.Id);
        if(!allowed){voiceText.Text="這段語音尚未解鎖。";return;}
        var record=Data.Items(Catalog(Data.Text(selected["sys_id"]))["voices"]).Select(Data.Map).First(d=>Data.Text(d["id"])==choice.Id);
        voiceText.Text=Data.Text(record["content"])+"\r\n\r\n音訊播放尚未接入此 Windows 預覽版。";
    }
    async Task ChangeSkin() {
        if(selected==null||skins.SelectedItem==null||connection==null)return;saveSkin.Enabled=false;
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
        if(connection==null||team==null)return;saveTeam.Enabled=false;
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
            using(var image=new Bitmap(Width,Height)){DrawToBitmap(image,new Rectangle(0,0,Width,Height));image.Save(Path.Combine(folder,"preview.png"),ImageFormat.Png);}
            File.WriteAllText(result,Data.Json.Serialize(Data.Obj("success",true,"characters",cards.Count,"files",Data.Items(unlocks["char_list"]).Count,"voices",Data.Items(unlocks["voice_list"]).Count,"team_loaded",team!=null,"skin_saved",true,"team_saved",true,"reconnect_verified",true,"native_windows",true,"battle_supported",false)),System.Text.Encoding.UTF8);
        }catch(Exception ex){File.WriteAllText(result,Data.Json.Serialize(Data.Obj("success",false,"error",ex.ToString())));}
        finally{Close();}
    }
    [STAThread]public static void Main(string[] args) {
        Application.EnableVisualStyles();Application.SetCompatibleTextRenderingDefault(false);
        try{Application.Run(new ClientWindow(Path.Combine(AppDomain.CurrentDomain.BaseDirectory,"data"),args.Contains("--smoke-test")));}
        catch(Exception ex){if(args.Contains("--smoke-test")){File.WriteAllText(Path.Combine(AppDomain.CurrentDomain.BaseDirectory,"startup-error.txt"),ex.ToString());Environment.ExitCode=1;}
            else MessageBox.Show("無法啟動 Windows 預覽版："+ex.Message,"Core Licht",MessageBoxButtons.OK,MessageBoxIcon.Error);}
    }
}
}
