using System;
using System.IO;
using System.Linq;
using System.Collections.Generic;
using System.Drawing;
using System.Drawing.Drawing2D;
using System.Windows.Forms;

namespace CoreLicht {
// All layout and pointer coordinates use the phone's 2340 x 1080 reference space.
// Letterboxing keeps the same composition on differently shaped desktop windows.
sealed class GameSurface:Control {
    public Action<Graphics> Render;
    public Action<PointF> Press;
    public Action<int> Scroll;
    public GameSurface(){DoubleBuffered=true;ResizeRedraw=true;TabStop=true;BackColor=Color.Black;}
    float ScaleFactor { get{return Math.Min(Width/2340f,Height/1080f);} }
    protected override void OnPaint(PaintEventArgs e){base.OnPaint(e);float scale=ScaleFactor;if(scale<=0)return;
        e.Graphics.TranslateTransform((Width-2340*scale)/2,(Height-1080*scale)/2);e.Graphics.ScaleTransform(scale,scale);
        e.Graphics.SetClip(new Rectangle(0,0,2340,1080));e.Graphics.SmoothingMode=SmoothingMode.AntiAlias;
        e.Graphics.InterpolationMode=InterpolationMode.HighQualityBicubic;e.Graphics.TextRenderingHint=System.Drawing.Text.TextRenderingHint.AntiAliasGridFit;
        if(Render!=null)Render(e.Graphics);
    }
    protected override void OnMouseDown(MouseEventArgs e){base.OnMouseDown(e);Focus();float s=ScaleFactor;if(s<=0)return;
        var p=new PointF((e.X-(Width-2340*s)/2)/s,(e.Y-(Height-1080*s)/2)/s);
        if(p.X>=0&&p.X<=2340&&p.Y>=0&&p.Y<=1080&&Press!=null)Press(p);
    }
    protected override void OnMouseWheel(MouseEventArgs e){base.OnMouseWheel(e);if(Scroll!=null)Scroll(e.Delta);}
}

public partial class ClientWindow {
    GameSurface gameView;
    readonly Dictionary<string,Image> artCache=new Dictionary<string,Image>();
    readonly Queue<string> artOrder=new Queue<string>();
    readonly Dictionary<string,string> currency=new Dictionary<string,string>();
    Dictionary<string,object> uiCharacters=new Dictionary<string,object>();
    readonly List<Tuple<RectangleF,Action>> hitAreas=new List<Tuple<RectangleF,Action>>();
    string screen="Home",playerName="",playerLevel="—",energy="—",energyMax="—",notice="";
    int rosterOffset,textOffset,editingSlot=-1;
    bool showVoice,hideHomeCharacter;
    static readonly Color Cream=Color.FromArgb(238,226,187),Dark=Color.FromArgb(22,23,22);

    void Build(){
        // These collections keep the protocol-facing selection logic independent of rendering.
        account.Text="windows-preview";
        string metadata=Path.Combine(folder,"ui/characters.json");if(File.Exists(metadata))uiCharacters=Data.Read(metadata);
        files.SelectedIndexChanged+=(s,e)=>{readTask=ReadFile();if(gameView!=null)gameView.Invalidate();};
        voices.SelectedIndexChanged+=(s,e)=>{ReadVoice();if(gameView!=null)gameView.Invalidate();};
        for(int i=0;i<8;i++)slots.Add(new ComboBox{DropDownStyle=ComboBoxStyle.DropDownList});
        gameView=new GameSurface{Dock=DockStyle.Fill};Controls.Add(gameView);
        gameView.Render=DrawGame;gameView.Press=ClickGame;
        SetupGameplay();
        gameView.Scroll=delta=>{if(screen=="Roster")rosterOffset=Math.Max(0,Math.Min(Math.Max(0,(cards.Count+6)/7-2),rosterOffset+(delta<0?1:-1)));
            else if(screen=="Files")textOffset=Math.Max(0,Math.Min(MaxTextOffset(),textOffset+(delta<0?100:-100)));gameView.Invalidate();};
        KeyPreview=true;KeyDown+=(s,e)=>{if(e.KeyCode==Keys.Escape){notice="";Navigate(screen=="Home"?"Home":"Roster");}
            if(e.KeyCode==Keys.F11){bool full=FormBorderStyle!=FormBorderStyle.None;FormBorderStyle=full?FormBorderStyle.None:FormBorderStyle.Sizable;WindowState=full?FormWindowState.Maximized:FormWindowState.Normal;}};
        FormClosed+=(s,e)=>{foreach(var image in artCache.Values)image.Dispose();};
    }
    void Navigate(string page){screen=page;notice="";textOffset=0;gameView.Invalidate();}
    Image Art(string path){Image value;if(artCache.TryGetValue(path,out value))return value;string full=Path.Combine(folder,path);
        if(!File.Exists(full))return null;using(var source=Image.FromFile(full))value=new Bitmap(source);
        while(artOrder.Count>=64){string oldest=artOrder.Dequeue();artCache[oldest].Dispose();artCache.Remove(oldest);}
        artCache[path]=value;artOrder.Enqueue(path);return value;}
    void Sprite(Graphics g,string name,float x,float y,float w,float h){var image=Art("ui/"+name+".png");if(image!=null)g.DrawImage(image,x,y,w,h);}
    void Rect(Graphics g,Color c,float x,float y,float w,float h){using(var b=new SolidBrush(c))g.FillRectangle(b,x,y,w,h);}
    void Line(Graphics g,Color c,float x,float y,float x2,float y2,float width){using(var p=new Pen(c,width))g.DrawLine(p,x,y,x2,y2);}
    void TextAt(Graphics g,string text,float size,Color color,float x,float y,float w,float h,bool center=false){
        using(var font=new Font("Microsoft JhengHei UI",size,FontStyle.Regular,GraphicsUnit.Pixel))
        using(var brush=new SolidBrush(color))using(var format=new StringFormat{Alignment=center?StringAlignment.Center:StringAlignment.Near,LineAlignment=StringAlignment.Center,Trimming=StringTrimming.EllipsisCharacter})
            g.DrawString(text,font,brush,new RectangleF(x,y,w,h),format);
    }
    void Hit(float x,float y,float w,float h,Action click){hitAreas.Add(Tuple.Create(new RectangleF(x,y,w,h),click));}
    void Button(Graphics g,string text,float x,float y,float w,float h,Action click,bool gold=false){
        Rect(g,gold?Color.FromArgb(170,164,143,92):Color.FromArgb(160,16,18,18),x,y,w,h);
        using(var p=new Pen(Color.FromArgb(140,Cream),1.5f))g.DrawRectangle(p,x,y,w,h);
        TextAt(g,text,32,Color.WhiteSmoke,x,y,w,h,true);Hit(x,y,w,h,click);
    }
    void ClickGame(PointF p){if(notice.Length>0){if(new RectangleF(1000,590,340,65).Contains(p)){notice="";gameView.Invalidate();}return;}
        for(int i=hitAreas.Count-1;i>=0;i--)if(hitAreas[i].Item1.Contains(p)){hitAreas[i].Item2();gameView.Invalidate();return;}}
    string CharacterName(Dictionary<string,object> c){return Data.Text(Catalog(Data.Text(c["sys_id"]))["name"]);}
    Image Portrait(Dictionary<string,object> c){if(c==null)return null;var info=Catalog(Data.Text(c["sys_id"]));var skin=Data.Map(Data.Map(info["skins"])[Data.Text(c["use_skin"])]);return Art(Data.Text(skin["image"]));}
    Image CardPortrait(Dictionary<string,object> c){var info=Catalog(Data.Text(c["sys_id"]));var skin=Data.Map(Data.Map(info["skins"])[Data.Text(c["use_skin"])]);
        return Art("ui/card_pic_"+Path.GetFileNameWithoutExtension(Data.Text(skin["image"]))+".png");}
    void FitArt(Graphics g,Image image,RectangleF box){if(image==null)return;float s=Math.Min(box.Width/image.Width,box.Height/image.Height);g.DrawImage(image,box.X+(box.Width-image.Width*s)/2,box.Y+(box.Height-image.Height*s)/2,image.Width*s,image.Height*s);}
    void DrawGame(Graphics g){
        hitAreas.Clear();if(screen=="Home")DrawHome(g);else{
            DrawInterior(g);if(screen=="Stages")DrawStages(g);else if(screen=="Battle")DrawBattle(g);else if(screen=="Result")DrawBattleResult(g);else if(screen=="Roster")DrawRoster(g);else if(screen=="Team")DrawTeam(g);else if(selected!=null){
                Image portrait=Portrait(selected);
                if(screen=="Skins"&&skins.SelectedItem!=null){var meta=Data.Map(Data.Map(Catalog(Data.Text(selected["sys_id"]))["skins"])[((Choice)skins.SelectedItem).Id]);portrait=Art(Data.Text(meta["image"]));}
                FitArt(g,portrait,new RectangleF(720,70,1510,1300));
                if(portrait==null)TextAt(g,"這套造型的立繪尚未取得",32,Cream,1000,350,900,180,true);
                if(screen=="Detail")DrawDetail(g);else if(screen=="Files")DrawFiles(g);else if(screen=="Skins")DrawSkins(g);
            }DrawHeader(g);
        }
        if(status.Text.StartsWith("連線失敗")||status.Text.StartsWith("連線已中斷")){
            Rect(g,Color.FromArgb(235,24,24,24),370,410,1600,220);TextAt(g,status.Text,28,Color.White,420,425,1500,100,true);
            Button(g,"重新連線",960,540,420,65,async()=>await Connect(),true);
        }else if(cards.Count==0)TextAt(g,"正在連線…",35,Cream,700,420,940,180,true);
        if(notice.Length>0){Rect(g,Color.FromArgb(175,0,0,0),0,0,2340,1080);Rect(g,Color.FromArgb(245,30,31,29),570,380,1200,320);
            TextAt(g,notice,32,Color.White,620,400,1100,160,true);Button(g,"確定",1000,590,340,65,()=>notice="",true);}
    }
    void DrawHome(Graphics g){
        var bg=Art("ui/main_c_bg.png");if(bg!=null)g.DrawImage(bg,new RectangleF(0,0,2340,1080),new RectangleF(0,450,bg.Width,bg.Width*1080f/2340),GraphicsUnit.Pixel);else Rect(g,Dark,0,0,2340,1080);
        var poster=cards.FirstOrDefault(c=>Data.Text(c["sys_id"])=="3008")??cards.FirstOrDefault();
        if(!hideHomeCharacter)FitArt(g,Portrait(poster),new RectangleF(520,80,1500,1300));
        Rect(g,Color.FromArgb(165,0,0,0),0,0,2340,90);Line(g,Cream,0,90,2340,90,2);
        Sprite(g,"main_c_icon_rhombus",245,15,45,45);TextAt(g,"Lv."+playerLevel+"   "+playerName,41,Color.White,295,0,900,70);
        Line(g,Color.FromArgb(150,Cream),270,72,710,72,4);
        string[] keys={"501","502","505"};string[] icons={"common_c_icon_coin","common_c_icon_yishimozu","common_c_icon_jiejing"};
        for(int i=0;i<keys.Length;i++){Sprite(g,icons[i],1390+i*255,18,45,45);TextAt(g,Get(currency,keys[i]),37,Cream,1450+i*255,7,190,70);}
        TextAt(g,"本機預覽",21,Color.FromArgb(170,Color.White),270,92,400,42);
        Sprite(g,"main_c_icon_drawer1",240,115,95,95);
        Sprite(g,"main_c_icon_replacement",248,543,70,70);Hit(235,530,90,90,()=>{Navigate("Roster");});
        Sprite(g,"main_c_icon_hide",345,543,70,70);Hit(330,530,100,90,()=>hideHomeCharacter=!hideHomeCharacter);
        Button(g,"任務",1905,365,190,70,()=>notice="任務頁尚未接入 Windows 版。");
        Button(g,"編隊",1905,468,190,70,()=>Navigate("Team"));
        Button(g,"物資",1905,571,190,70,()=>notice="物資頁尚未接入 Windows 版。");
        Sprite(g,"common_c_icon_vitality_big",1745,860,65,65);
        TextAt(g,energy,58,Color.White,1820,848,130,85);TextAt(g,"精神力\n/"+energyMax,23,Color.White,1945,855,150,75);
        DrawBottom(g,new[]{"空島","商店","共鳴","適格體","超體","作戰"},3,idx=>{
            if(idx==3){editingSlot=-1;Navigate("Roster");}else if(idx==5)Navigate("Stages");else notice="此頁面尚未接入 Windows 版。";
        },true);
    }
    void DrawInterior(Graphics g){
        using(var brush=new LinearGradientBrush(new Rectangle(0,0,2340,1080),Color.FromArgb(171,177,177),Color.FromArgb(9,11,11),-20f))g.FillRectangle(brush,0,0,2340,1080);
        using(var brush=new LinearGradientBrush(new Rectangle(0,0,2340,1080),Color.Transparent,Color.White,90f)){
            brush.InterpolationColors=new ColorBlend{Positions=new[]{0f,.37f,1f},Colors=new[]{Color.Transparent,Color.Transparent,Color.FromArgb(185,238,238,237)}};
            g.FillRectangle(brush,0,0,2340,1080);}
        // The subdued geometric motif mirrors the character page without obscuring the portrait.
        using(var p=new Pen(Color.FromArgb(24,Cream),2)){for(int r=120;r<=410;r+=65)g.DrawEllipse(p,1750-r,445-r,r*2,r*2);
            for(int i=0;i<12;i++){double a=i*Math.PI/6;g.DrawLine(p,1750,445,1750+(float)Math.Cos(a)*410,445+(float)Math.Sin(a)*410);}}
    }
    void DrawHeader(Graphics g){
        Rect(g,Color.FromArgb(170,0,0,0),0,0,2340,88);Line(g,Color.FromArgb(100,Cream),0,88,2340,88,2);
        TextAt(g,"◀ 返回",35,Cream,145,5,200,70);Hit(130,0,220,88,()=>{editingSlot=-1;Navigate(screen=="Battle"||screen=="Result"?"Stages":screen=="Stages"||screen=="Roster"||screen=="Team"?"Home":screen=="Files"||screen=="Skins"?"Detail":"Roster");});
        TextAt(g,"○ 主頁",35,Cream,390,5,220,70);Hit(370,0,240,88,()=>{editingSlot=-1;Navigate("Home");});
        if(screen=="Roster"){
            TextAt(g,cards.Count.ToString(),29,Cream,1190,0,90,80,true);
            Button(g,"等級 ↓",1368,18,180,57,()=>{cards=cards.OrderByDescending(c=>Data.Number(c["lvl"])).ToList();});
            Button(g,"星數",1548,18,180,57,()=>{cards=cards.OrderByDescending(c=>Data.Number(c["star"])).ToList();});
            Button(g,"獲得順序",1728,18,240,57,()=>{cards=cards.OrderBy(c=>Data.Number(c["id"])).ToList();});
            Button(g,"篩選",2010,18,200,57,()=>{notice="目前顯示全部 "+cards.Count+" 名適格體。";});
        }else TextAt(g,screen=="Stages"||screen=="Battle"||screen=="Result"?"作戰演習 · 原型規則":screen=="Team"?"編隊":selected==null?"":CharacterName(selected),27,Cream,1730,0,480,80);
    }
    void DrawBottom(Graphics g,string[] names,int active,Action<int> click,bool home=false){
        Rect(g,Color.FromArgb(200,13,14,13),0,930,2340,150);Line(g,Cream,0,930,2340,930,2);
        float start=250,width=315;
        for(int i=0;i<names.Length;i++){int index=i;float x=start+i*width;bool chosen=i==active;
            if(home&&i==5)Sprite(g,"BattleBth_30",x-10,931,width+90,149);
            else{if(chosen){Rect(g,Color.FromArgb(48,Cream),x,932,width,148);Sprite(g,"main_c_bg_frame",x+30,938,width-60,142);}
                Line(g,Color.FromArgb(90,Cream),x+width,955,x+width,1060,1);}
            TextAt(g,names[i],38,chosen||home&&i==5?Color.White:Cream,x,955,width,90,true);
            Hit(x,932,width,148,()=>click(index));
        }
    }
    void DrawRoster(Graphics g){
        var state=g.Save();g.SetClip(new Rectangle(0,100,2340,950));
        for(int i=0;i<cards.Count;i++){int index=i;int row=i/7-rosterOffset;if(row<0||row>2)continue;
            float x=290+(i%7)*249,y=126+row*447;DrawCard(g,cards[i],x,y,200,396);
            Hit(x,y,200,Math.Min(396,1050-y),()=>{if(editingSlot>=0){int slot=editingSlot;
                string id=Data.Text(cards[index]["id"]);for(int j=0;j<slots[slot].Items.Count;j++)if(((Choice)slots[slot].Items[j]).Id==id)slots[slot].SelectedIndex=j;
                editingSlot=-1;Navigate("Team");}else{SelectCard(cards[index]);Navigate("Detail");}});
        }g.Restore(state);
        Rect(g,Color.FromArgb(110,35,36,35),116,150,10,790);float thumb=Math.Max(60,790f*2/Math.Max(2,(cards.Count+6)/7));
        Rect(g,Color.FromArgb(180,200,200,195),116,150+rosterOffset*(790-thumb)/Math.Max(1,(cards.Count+6)/7-2),10,thumb);
        TextAt(g,editingSlot>=0?"選擇第 "+(editingSlot+1)+" 位角色":"滾動滑鼠捲輪瀏覽適格體",22,Color.FromArgb(180,Color.White),290,1036,1200,40);
    }
    void DrawCard(Graphics g,Dictionary<string,object> card,float x,float y,float w,float h){
        Rect(g,Color.FromArgb(170,18,22,23),x+7,y+9,w,h);Rect(g,Color.FromArgb(85,87,90),x,y,w,h);
        var image=CardPortrait(card);if(image!=null){var state=g.Save();g.SetClip(new RectangleF(x,y,w,h));
            g.DrawImage(image,x,y,w,h);g.Restore(state);
        }else TextAt(g,"立繪尚未取得",20,Cream,x,y+100,w,120,true);
        using(var b=new LinearGradientBrush(new RectangleF(x,y+h-155,w,155),Color.Transparent,Color.FromArgb(225,196,126,214),90f))g.FillRectangle(b,x,y+h-155,w,155);
        using(var p=new Pen(Color.FromArgb(185,Cream),2))g.DrawRectangle(p,x,y,w,h);
        object metadata;if(uiCharacters.TryGetValue(Data.Text(card["sys_id"]),out metadata)){
            Sprite(g,"card_c_occIcon_bg01_128",x-14,y+14,62,62);Sprite(g,Data.Text(Data.Map(metadata)["job_icon"]),x-10,y+18,54,54);}
        using(var p=new Pen(Color.FromArgb(125,Cream),2))g.DrawPolygon(p,new[]{new PointF(x+w/2,y+h-145),new PointF(x+w/2+43,y+h-101),new PointF(x+w/2,y+h-57),new PointF(x+w/2-43,y+h-101)});
        TextAt(g,Data.Text(card["lvl"]),38,Color.White,x,y+h-138,w,76,true);
        TextAt(g,CharacterName(card),29,Color.White,x+4,y+h-56,w-8,50,true);
    }
    void DrawDetail(Graphics g){
        if(selected==null)return;
        var attrs=Data.Items(selected["attr"]).Select(Data.Map).ToDictionary(a=>Data.Text(a["k"]),a=>Data.Text(a["v"]));
        Rect(g,Color.FromArgb(160,232,232,226),245,130,470,95);
        TextAt(g,Data.Text(selected["lvl"]),58,Dark,270,136,170,80,true);TextAt(g,"/ "+Data.Text(selected["lvl"]),34,Color.FromArgb(90,90,85),450,136,240,80);
        string[] labels={"生命","攻擊","防禦","好感度"};string[] values={Get(attrs,"11"),Get(attrs,"12"),Get(attrs,"14"),Data.Text(selected["favor_lvl"])};
        for(int i=0;i<4;i++){float x=245+(i%2)*290,y=247+(i/2)*74;TextAt(g,"◇ "+labels[i],31,Cream,x,y,175,64);TextAt(g,values[i],32,Color.White,x+170,y,130,64);}
        object metadata;if(uiCharacters.TryGetValue(Data.Text(selected["sys_id"]),out metadata)){
            var meta=Data.Map(metadata);string[] labels2={"費用","攻速","目標","移速","移動","傷害"};string[] fields={"cost","attack_speed","target","speed","move_style","hurt"};
            for(int i=0;i<6;i++){float x=245+(i%2)*290,y=398+(i/2)*64;TextAt(g,labels2[i],29,Cream,x,y,170,60);TextAt(g,Data.Text(meta[fields[i]]),29,Color.White,x+170,y,130,60);}
        }
        TextAt(g,"角色屬性",25,Color.FromArgb(75,76,72),245,585,480,55,true);
        Rect(g,Color.FromArgb(100,38,39,37),245,660,480,155);TextAt(g,"＋ 未裝備閃存體",34,Color.White,245,660,480,155,true);
        Rect(g,Color.FromArgb(100,220,220,212),245,847,480,66);Sprite(g,"common_c_icon_favorabilty",265,858,45,45);TextAt(g,"好感度  "+Data.Text(selected["favor_lvl"]),32,Dark,325,847,360,66);
        Button(g,"▣ 檔案",1930,158,170,60,()=>{showVoice=false;Navigate("Files");});
        Button(g,"♧ 時裝",1930,265,170,60,()=>Navigate("Skins"));
        Rect(g,Color.FromArgb(215,8,9,8),1560,775,530,85);TextAt(g,CharacterName(selected),42,Cream,1580,785,500,70);
        Sprite(g,"common_c_icon_star"+Math.Min(6,Math.Max(3,Data.Number(selected["star"]))),1970,770,100,100);
        DrawBottom(g,new[]{"屬性","強化","突破","同調","閃存體","技能"},0,i=>{if(i!=0)notice="此功能仍在重建；目前可查看屬性、檔案與時裝。";});
    }
    ListBox ActiveDocuments {get{return showVoice?voices:files;}}
    string ActiveText {get{return showVoice?voiceText.Text:fileText.Text;}}
    int MaxTextOffset(){using(var b=new Bitmap(1,1))using(var g=Graphics.FromImage(b))using(var font=new Font("Microsoft JhengHei UI",29,FontStyle.Regular,GraphicsUnit.Pixel))
        return Math.Max(0,(int)g.MeasureString(ActiveText,font,850).Height-640);}
    void DrawFiles(Graphics g){
        Rect(g,Color.FromArgb(222,230,230,222),225,175,1420,695);
        Button(g,"資料檔案",245,112,260,62,()=>{showVoice=false;textOffset=0;},!showVoice);
        Button(g,"語音台詞",520,112,260,62,()=>{showVoice=true;textOffset=0;},showVoice);
        var list=ActiveDocuments;int start=list.SelectedIndex>9?list.SelectedIndex-9:0;
        for(int i=start;i<Math.Min(list.Items.Count,start+10);i++){int index=i;float y=200+(i-start)*61;var choice=(Choice)list.Items[i];
            bool chosen=i==list.SelectedIndex;Rect(g,chosen?Color.FromArgb(215,44,45,40):Color.FromArgb(70,125,125,116),245,y,410,52);
            TextAt(g,choice.Name,27,chosen?Cream:Dark,262,y,380,52);Hit(245,y,410,52,()=>{list.SelectedIndex=index;textOffset=0;});}
        if(list.Items.Count>10){Button(g,"上一項",245,816,195,45,()=>{if(list.SelectedIndex>0)list.SelectedIndex--;textOffset=0;});
            Button(g,"下一項",460,816,195,45,()=>{if(list.SelectedIndex<list.Items.Count-1)list.SelectedIndex++;textOffset=0;});}
        Line(g,Color.FromArgb(100,Dark),685,205,685,840,1);
        var state=g.Save();g.SetClip(new Rectangle(725,205,850,640));
        using(var font=new Font("Microsoft JhengHei UI",29,FontStyle.Regular,GraphicsUnit.Pixel))using(var brush=new SolidBrush(Dark))
            g.DrawString(ActiveText,font,brush,new RectangleF(725,205-textOffset,850,Math.Max(640,MaxTextOffset()+660)));
        g.Restore(state);TextAt(g,"滾輪捲動內文",21,Color.FromArgb(120,Color.Black),1270,868,340,40);
        DrawBottom(g,new[]{"檔案","語音","屬性","時裝","",""},showVoice?1:0,i=>{if(i<2){showVoice=i==1;textOffset=0;}else if(i==2)Navigate("Detail");else if(i==3)Navigate("Skins");});
    }
    void DrawSkins(Graphics g){
        TextAt(g,CharacterName(selected),58,Cream,250,180,600,100);
        TextAt(g,"時裝",35,Color.White,250,290,400,70);
        for(int i=0;i<skins.Items.Count;i++){int index=i;float y=405+i*88;var choice=(Choice)skins.Items[i];
            Button(g,choice.Name,250,y,640,72,()=>{skins.SelectedIndex=index;},i==skins.SelectedIndex);
        }
        Button(g,"穿戴",1900,825,220,80,async()=>{if(!saveSkin.Enabled)return;await ChangeSkin();if(status.Text!="造型已保存。")notice=status.Text;gameView.Invalidate();},true);
        TextAt(g,saveSkin.Enabled?status.Text=="造型已保存。"?"已穿戴":"選擇時裝後按「穿戴」":"正在保存…",24,Cream,1690,745,430,65,true);
        DrawBottom(g,new[]{"屬性","檔案","時裝","","",""},2,i=>{if(i==0)Navigate("Detail");else if(i==1)Navigate("Files");});
    }
    void DrawTeam(Graphics g){
        TextAt(g,"一般作戰隊伍",44,Cream,250,135,900,90);
        for(int i=0;i<8;i++){int index=i;float x=250+i*235;var choice=slots[i].SelectedItem as Choice;
            var member=choice==null?null:cards.FirstOrDefault(c=>Data.Text(c["id"])==choice.Id);
            if(member!=null)DrawCard(g,member,x,290,210,420);else{Rect(g,Color.FromArgb(110,25,26,24),x,290,210,420);TextAt(g,"＋",65,Cream,x,290,210,420,true);}
            TextAt(g,(i+1).ToString(),28,Cream,x,735,210,50,true);Hit(x,290,210,420,()=>{editingSlot=index;Navigate("Roster");});
            Button(g,"移除",x,800,210,55,()=>slots[index].SelectedIndex=0);
        }
        Button(g,"保存編隊",1810,940,310,90,async()=>{await SaveTeam();notice=status.Text;},true);
    }
    void VerifyGameNavigation(){
        int savedSlot=slots[0].SelectedIndex;
        Navigate("Home");RenderForInput();ClickGame(new PointF(1350,1000));RequireScreen("Roster");
        RenderForInput();ClickGame(new PointF(390,260));RequireScreen("Detail");
        RenderForInput();ClickGame(new PointF(2000,188));RequireScreen("Files");
        RenderForInput();ClickGame(new PointF(200,40));RequireScreen("Detail");
        RenderForInput();ClickGame(new PointF(2000,290));RequireScreen("Skins");
        RenderForInput();ClickGame(new PointF(450,40));RequireScreen("Home");
        RenderForInput();ClickGame(new PointF(2000,500));RequireScreen("Team");
        RenderForInput();ClickGame(new PointF(350,430));RequireScreen("Roster");
        RenderForInput();ClickGame(new PointF(390,260));RequireScreen("Team");
        slots[0].SelectedIndex=savedSlot;
        Navigate("Home");RenderForInput();ClickGame(new PointF(1980,1000));RequireScreen("Stages");
        Navigate("Home");notice="導覽提示測試";RenderForInput();ClickGame(new PointF(1350,1000));RequireScreen("Home");
        ClickGame(new PointF(1170,620));if(notice.Length!=0)throw new InvalidDataException("Dialog did not dismiss");
    }
    void RenderForInput(){using(var b=new Bitmap(gameView.Width,gameView.Height))gameView.DrawToBitmap(b,new Rectangle(0,0,b.Width,b.Height));}
    void RequireScreen(string expected){if(screen!=expected)throw new InvalidDataException("Navigation expected "+expected+", got "+screen);}
}
}
