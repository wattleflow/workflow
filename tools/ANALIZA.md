# WEM-LINT-ANALIZA

**Mjerenje modularnosti i sigurnosnih kompromisa: od mjere stanja do mjere odluke**

Oznaka autora: BT

---

## 1. Apstrakt

Dokument razmatra može li se arhitektonska granica u programskom sustavu kvantificirati tako da mjera bude formalno obranjiva, a ne samo brojčano izražena [[15]](https://openlibrary.org/isbn/9780124254015). Razlikuju se dvije vrste mjere: **mjera stanja**, koja opisuje zatečenu strukturu artefakta [[11]](https://doi.org/10.1016/j.respol.2012.04.011), i **mjera odluke**, koja procjenjuje isplativost pojedine granice pod neizvjesnošću [[6]](https://mitpress.mit.edu/9780262024662/design-rules/). Pokazuje se da mjera stanja nije jednostavnija po prirodi, nego zato što joj je dovoljan sam artefakt, dok mjera odluke zahtijeva distribuciju vjerojatnosti nad budućim stanjima svijeta [[6]](https://mitpress.mit.edu/9780262024662/design-rules/). Od razmatranih veličina samo tri imaju svojstva pravoga postotka: propagation cost [[11]](https://doi.org/10.1016/j.respol.2012.04.011), normalizirana uzajamna informacija između particija [[20]](https://doi.org/10.1088/1742-5468/2005/09/P09008) i Gordon–Loebova granica ulaganja [[26]](https://doi.org/10.1145/581271.581274). Dodatno se pokazuje da pojam volatilnosti krije tri različita fenomena, od kojih jedan — strateški protivnik — ruši pretpostavke opcijskih modela [[32]](https://doi.org/10.1007/978-3-642-12586-7). Sukob sigurnosti i udobnosti formalizira se kao problem izbora radne točke klasifikatora, a ne kao pitanje kvalitete mehanizma [[31]](https://doi.org/10.1109/TIT.1954.1057460). Zaključak je da jedinstveni skalarni indeks nije obranjiv, te se predlaže vektorski profil s Pareto-analizom [[16]](https://doi.org/10.1126/science.103.2684.677).

---

## 2. Uvod i glavna pitanja

Rasprava polazi od Parnasova kriterija prema kojem modul nije skupina srodnih funkcija, nego granica oko odluke koja se može promijeniti [[1]](https://doi.org/10.1145/361598.361623). Uz njega stoji Simonova teza o skoro-rastavljivosti, prema kojoj su interakcije unutar dijela znatno gušće od interakcija između dijelova [[2]](https://www.jstor.org/stable/985254). Treći okvir čine kohezija i sprezanje kao mjerljive kategorije strukturiranog dizajna [[3]](https://doi.org/10.1147/sj.132.0115). Četvrti se oslanja na ograničenja radne memorije i kognitivnog opterećenja čitatelja [[4]](https://doi.org/10.1037/h0043158)[[5]](https://doi.org/10.1207/s15516709cog1202_4).

Iz toga proizlaze tri glavna pitanja ovog dokumenta [S]:

1. Može li se stupanj modularnosti sustava izraziti kao postotak, i pod kojim uvjetima taj postotak zadržava značenje [[15]](https://openlibrary.org/isbn/9780124254015)?
2. Može li se isplativost pojedine arhitektonske odluke izraziti u istoj ili usporedivoj mjeri kao stanje [[6]](https://mitpress.mit.edu/9780262024662/design-rules/)?
3. Kako se pojam volatilnosti odnosi prema sigurnosti, i je li sukob sigurnosti i udobnosti mjerljiv [[26]](https://doi.org/10.1145/581271.581274)[[25]](https://doi.org/10.1145/1595676.1595684)?

Preduvjet svake od tih mjera jest reprezentacijski uvjet: mjera je homomorfizam iz empirijskog relacijskog sustava u numerički sustav [[15]](https://openlibrary.org/isbn/9780124254015). Bez prethodno definirane empirijske relacije oblika „A je modularniji od B” brojevi postoje, ali skala ne postoji [[19]](https://doi.org/10.1145/336512.336588). Aksiomatski okviri za vrednovanje metrika složenosti [[17]](https://doi.org/10.1109/32.4634) i za svojstveno utemeljeno mjerenje sprezanja i kohezije [[18]](https://doi.org/10.1109/32.481535) pokazuju da velik dio popularnih metrika taj uvjet ne zadovoljava.

---

## 3. Identificirane informacijske nepoznanice (information gaps)

Praznine su navedene jer određuju domet svakog indeksa izgrađenog na ovoj osnovi [S].

**3.1. Nedefiniran pojam volatilnosti.** U izvornoj raspravi pojam volatilnosti korišten je bez definicije, a pokriva najmanje tri različita fenomena [S]. Volatilnost zahtjeva ponaša se kao egzogeni stohastički proces [[6]](https://mitpress.mit.edu/9780262024662/design-rules/). Tehnološka volatilnost je također egzogena, ali sporija [[6]](https://mitpress.mit.edu/9780262024662/design-rules/). Volatilnost prijetnje je endogena i strateška, jer protivnik promatra arhitekturu i bira točku napada nakon odluke oko arhitekture[[32]](https://doi.org/10.1007/978-3-642-12586-7).

**3.2. Nemjerljiva jezgra složenosti.** Esencijalna složenost se granicama ne uklanja, nego premješta [[29]](https://doi.org/10.1109/MC.1987.1663532). Isti uvid u kibernetičkom obliku daje zakon nužne raznolikosti [[30]](http://pespmc1.vub.ac.be/books/IntroCyb.pdf). Svaki indeks koji tvrdi da je složenost uklonjena zapravo mjeri njezino premještanje [S].

**3.3. Nesumjerljivost jedinica.** Bitovi, novčane jedinice i sekunde ljudskog razumijevanja nemaju konverzijski tečaj [[16]](https://doi.org/10.1126/science.103.2684.677). Jedini okvir koji načelno nudi svođenje na jednu jedinicu jest opis minimalne duljine [[13]](https://doi.org/10.1016/0005-1098(78)90005-5).

**3.4. Ordinalnost većine strukturnih metrika.** Na ordinalnim skalama zbrajanje i prosjek nisu definirane operacije [[16]](https://doi.org/10.1126/science.103.2684.677). Time je ponderirani zbroj metrika formalno neispravan prije nego što je izračunat [[19]](https://doi.org/10.1145/336512.336588).

**3.5. Neizračunljivost teorijskog optimuma.** Kolmogorovljeva složenost nije izračunljiva i može se samo aproksimirati, u praksi kompresijskim postupcima [[14]](https://doi.org/10.1109/TIT.2005.844059).

**3.6. Rezolucijsko ograničenje mjera zajednica.** Modularnost *Q* sustavno ne prepoznaje male module unutar velikih grafova [[8]](https://doi.org/10.1073/pnas.0605965104).

**3.7. Erozija mjere pod upravljanjem.** Pokazatelj koji se koristi za upravljanje prestaje mjeriti ono što je mjerio [[22]](https://doi.org/10.1016/0149-7189(79)90048-X). U sigurnosnom kontekstu to znači prelazak mjerene sigurnosti u usklađenost s propisom, a usklađenost nije zaštita [[28]](https://doi.org/10.1109/ACSAC.2001.991552).

**3.8. Problem poticaja.** Znatan dio sigurnosnih neuspjeha nije problem mjerenja nego raspodjele poticaja, jer trošak snosi strana koja ne donosi odluku [[28]](https://doi.org/10.1109/ACSAC.2001.991552).

---

## 4. Metodologije

### 4.1. Preduvjeti mjerenja

Postupak započinje definiranjem vanjskog kriterija prije same metrike, primjerice troška promjene u satima, gustoće defekata po modulu ili vremena uvođenja novog člana tima [[19]](https://doi.org/10.1145/336512.336588). Zatim se formalizira empirijska relacija koja operativno uređuje objekte prije njihova numeričkog prikaza [[15]](https://openlibrary.org/isbn/9780124254015). Nakon toga provjerava se homomorfizam i utvrđuje tip skale te se bilježe dopuštene statistike [[16]](https://doi.org/10.1126/science.103.2684.677). Prediktivna valjanost provjerava se na uzorku različitom od onoga na kojem je pokazatelj kalibriran [[19]](https://doi.org/10.1145/336512.336588). Stabilnost se testira osjetljivošću na granulaciju entiteta, vremenski prozor povijesti i rezolucijski parametar [[8]](https://doi.org/10.1073/pnas.0605965104). Naposljetku se dijagnostička uporaba odvaja od upravljačke, jer prva preživljava, a druga korodira [[22]](https://doi.org/10.1016/0149-7189(79)90048-X).

### 4.2. Dva grafa kao metodološka osnova

Metodološki ključ jest promatranje istoga sustava kroz dva različita grafa [S]. Prvi je graf statičkih ovisnosti, koji bilježi tko koga poziva ili uvozi [[11]](https://doi.org/10.1016/j.respol.2012.04.011). Drugi je graf su-promjena izveden iz povijesti sustava za upravljanje verzijama [[9]](https://doi.org/10.1109/ICSM.1998.738508)[[10]](https://doi.org/10.1109/TSE.2005.72). Svaki graf daje vlastitu particiju modula postupcima otkrivanja zajednica [[7]](https://doi.org/10.1103/PhysRevE.69.026113). Njihovo se neslaganje kvantificira standardnim mjerama usporedbe particija, ponajprije normaliziranom uzajamnom informacijom [[20]](https://doi.org/10.1088/1742-5468/2005/09/P09008) i prilagođenim Randovim indeksom [[21]](https://doi.org/10.1007/BF01908075).

### 4.3. Mjerenje kognitivne strane

Kognitivna komponenta ne mjeri se na kodu nego na čitatelju [S]. Klasična ograničenja kapaciteta radne memorije daju gornju granicu broja istodobno praćenih elemenata [[4]](https://doi.org/10.1037/h0043158). Teorija kognitivnog opterećenja razlikuje suvišno od nužnog opterećenja i upozorava da kriva dekompozicija povećava prvo [[5]](https://doi.org/10.1207/s15516709cog1202_4). Empirijski je moguće mjeriti vrijeme razumijevanja te aktivacijske obrasce tijekom čitanja izvornog koda [[33]](https://doi.org/10.1145/2568225.2568252).

### 4.4. Mjerenje informacijskog sadržaja podjele

Entropijske mjere kohezije i sprezanja daju rezultat izražen u bitovima [[12]](https://doi.org/10.1109/METRIC.1999.809743). Kriterij minimalne duljine opisa nalaže da je podjela opravdana ako je zbroj opisa dijelova i opisa sučelja kraći od opisa cjeline [[13]](https://doi.org/10.1016/0005-1098(78)90005-5). Iz toga slijedi da postoji točka nakon koje daljnje usitnjavanje povećava ukupnu složenost, jer sučelja rastu brže od uštede [[13]](https://doi.org/10.1016/0005-1098(78)90005-5). Praktična aproksimacija provodi se normaliziranom kompresijskom udaljenošću [[14]](https://doi.org/10.1109/TIT.2005.844059).

### 4.5. Mjerenje sigurnosne strane

Napadna površina formalno se mjeri preko metoda, kanala i podatkovnih stavki izloženih izvan granice sustava [[27]](https://doi.org/10.1109/TSE.2010.60). Ekonomska strana modelira se funkcijom ranjivosti i očekivanog gubitka [[26]](https://doi.org/10.1145/581271.581274). Ljudska strana mjeri se proračunom usklađenosti, odnosno konačnim proračunom truda koji korisnik može uložiti u sigurnosne postupke [[25]](https://doi.org/10.1145/1595676.1595684). Najizravniji pojedinačni pokazatelj je stopa zaobilaženja mehanizma, jer je ishod, a ne stav [[24]](https://doi.org/10.1145/322796.322806). Radna točka kontrole opisuje se odnosom lažno pozitivnih i lažno negativnih ishoda unutar teorije detekcije [[31]](https://doi.org/10.1109/TIT.1954.1057460).

---

## 5. Analiza

### 5.1. Što se legitimno izražava postotkom

Mjera stanja je lakša ne zato što je jednostavnija, nego zato što joj je dovoljan sam artefakt [S]. Mjera odluke traži distribuciju vjerojatnosti nad budućnostima, dakle model svijeta, a ne model koda [[6]](https://mitpress.mit.edu/9780262024662/design-rules/). Od razmatranih veličina, propagation cost je doslovno udio parova komponenti povezanih tranzitivnom ovisnošću i time postotak sustava u dosegu prosječne promjene [[11]](https://doi.org/10.1016/j.respol.2012.04.011). Normalizirana uzajamna informacija kreće se u rasponu od nule do jedan i izražava stupanj poklapanja strukture i promjene [[20]](https://doi.org/10.1088/1742-5468/2005/09/P09008). Gordon–Loebova granica jedini je postotak koji izravno odgovara na pitanje isplativosti [[26]](https://doi.org/10.1145/581271.581274). Modularnost *Q*, kohezija i veličina modula nisu postoci koliko god njihov raspon tako izgledao [[16]](https://doi.org/10.1126/science.103.2684.677).

### 5.2. Most između stanja i odluke

Mjere stanja ne treba prevoditi u mjere odluke, jer su one ulaz u njih [S]:

$$E[\text{trošak promjene}] = \underbrace{\text{propagation cost}}_{\text{stanje}} \times \underbrace{\lambda_{\text{promjene}}}_{\text{volatilnost}} \times \underbrace{c}_{\text{jedinični trošak}}$$

Struktura daje doseg posljedice [[11]](https://doi.org/10.1016/j.respol.2012.04.011), dok volatilnost daje učestalost događaja [[10]](https://doi.org/10.1109/TSE.2005.72). Izraz je dimenzionalno konzistentan, a obje se strane mjere iz različitih izvora — koda i povijesti verzija [[9]](https://doi.org/10.1109/ICSM.1998.738508). Isti se oblik prenosi na sigurnosnu domenu gotovo bez izmjene [[26]](https://doi.org/10.1145/581271.581274).

### 5.3. Volatilnost kao tri različita pojma

| Pojam | Priroda | Ponaša se kao | Izvor |
|---|---|---|---|
| Volatilnost zahtjeva | varijanca vrijednosti zahtjeva | egzogeni stohastički proces | [[6]](https://mitpress.mit.edu/9780262024662/design-rules/) |
| Tehnološka volatilnost | promjena platformi i ovisnosti | egzogen, spor proces | [[6]](https://mitpress.mit.edu/9780262024662/design-rules/) |
| Volatilnost prijetnje | protivnik koji optimizira protiv sustava | strateški, endogen proces | [[32]](https://doi.org/10.1007/978-3-642-12586-7) |

Modeli realnih opcija nasljeđuju financijsku pretpostavku da priroda nije strateška te da je volatilnost egzogena i stacionarna [[6]](https://mitpress.mit.edu/9780262024662/design-rules/). Za sigurnost ta pretpostavka ne vrijedi, jer protivnik promatra arhitekturu i bira točku napada nakon odluke branitelja [[32]](https://doi.org/10.1007/978-3-642-12586-7). Posljedica je da opcijski modeli sustavno podcjenjuju sigurnosni rizik, budući da tretiraju varijancu kao zadanu, a ona je funkcija same odluke [S]. Napadna površina stoga ne trpi napade nego ih privlači [[27]](https://doi.org/10.1109/TSE.2010.60). Dosljedan formalizam nije opcijski nego igra s vođom i sljedbenikom, u kojoj branitelj bira prvi, a protivnik odgovara najboljim odgovorom [[32]](https://doi.org/10.1007/978-3-642-12586-7). Time se mijenja i kriterij optimalnosti, jer se umjesto očekivane vrijednosti primjenjuje minimaks nad protivnikovim najboljim odgovorom [[32]](https://doi.org/10.1007/978-3-642-12586-7).

### 5.4. Sigurnost i udobnost kao problem detekcije

Svaka sigurnosna kontrola formalno je klasifikator [[31]](https://doi.org/10.1109/TIT.1954.1057460). Sukob nije filozofski nego se svodi na dvije vrste pogreške: lažno pozitivan ishod blokira legitimnog korisnika i stvara trošak udobnosti [[24]](https://doi.org/10.1145/322796.322806), dok lažno negativan ishod propušta napadača i stvara trošak proboja [[26]](https://doi.org/10.1145/581271.581274). Teorija detekcije signala daje radnu točku u obliku:

$$\frac{P(\text{signal})}{P(\text{šum})} \cdot \frac{C_{FN}}{C_{FP}} = \text{prag}$$

Iz toga slijedi da postroženost sama po sebi nije mjera kvalitete, jer je pomak praga kretanje po istoj krivulji, a ne poboljšanje [[31]](https://doi.org/10.1109/TIT.1954.1057460). Stvarno poboljšanje jest pomak same krivulje, dakle bolji senzor ili bogatiji kontekst [[31]](https://doi.org/10.1109/TIT.1954.1057460). Većina rasprava o sigurnosti i udobnosti zapravo je neslaganje o radnoj točki prikazano kao neslaganje o kvaliteti [S]. Drugi ključan uvid tiče se osnovne stope: pri niskoj prevalenciji napada i vrlo dobar klasifikator daje pretežno lažne uzbune [[31]](https://doi.org/10.1109/TIT.1954.1057460). To objašnjava zašto sigurnosne kontrole erodiraju u praksi, a razlog nije nedisciplina korisnika [[24]](https://doi.org/10.1145/322796.322806). Korisnik raspolaže konačnim proračunom truda, pa njegovo prekoračenje ne proizvodi otpor nego zaobilaženje [[25]](https://doi.org/10.1145/1595676.1595684). Vrijedi primjetiti da je psihološka prihvatljivost već izvorno navedena među temeljnim načelima zaštite, a ne kao naknadni kompromis [[23]](https://doi.org/10.1109/PROC.1975.9939). Mehanizam koji se sustavno zaobilazi ne štiti [[24]](https://doi.org/10.1145/322796.322806).

### 5.5. Spajanje modularnosti i sigurnosti

Očekivani gubitak ima isti oblik kao očekivani trošak promjene [S]:

$$E[L] = \sum_i P(\text{kompromitacija}_i) \cdot \text{Blast}(i) \cdot V$$

Veličina Blast(a) izvodi se iz dosezljivosti u grafu ovisnosti i povlastica, dakle iz istih strukturnih mjera kao i propagation cost [[11]](https://doi.org/10.1016/j.respol.2012.04.011). Modularnost time prestaje biti estetsko pitanje i postaje množitelj u računu rizika [S]. Postoji, međutim, zrcalna napetost analogna onoj kod minimalne duljine opisa [S]. Dekompozicija smanjuje domet proboja kroz kompartmentalizaciju i načelo najmanje povlastice [[23]](https://doi.org/10.1109/PROC.1975.9939). Istodobno povećava broj sučelja, a svako je sučelje ulazna točka [[27]](https://doi.org/10.1109/TSE.2010.60). Optimum je stoga unutarnji, a ne rubni, što je isti zaključak kao kod kriterija minimalne duljine opisa, izveden neovisnim putem [[13]](https://doi.org/10.1016/0005-1098(78)90005-5). Dodatna je zamka da moduli koji dijele istu ovisnost imaju korelirane proboje, pa nominalna izolacija bez izolacije lanca opskrbe ostaje prividna [[34]](https://nvd.nist.gov/vuln/detail/CVE-2021-44228). Domet proboja mora se stoga računati na grafu koji uključuje tranzitivne ovisnosti, a ne samo vlastiti kod [[34]](https://nvd.nist.gov/vuln/detail/CVE-2021-44228).

### 5.6. Postotak koji stvarno postoji

Gordon–Loebov model daje rezultat prema kojem optimalno ulaganje u sigurnost ne prelazi približno 37 posto, odnosno 1/e očekivanog gubitka [[26]](https://doi.org/10.1145/581271.581274). Rezultat je izveden iz opadajućih prinosa funkcije ranjivosti [[26]](https://doi.org/10.1145/581271.581274). Praktična mu je vrijednost što daje strop, a ne cilj, te što implicira da najranjivija imovina nije nužno ona u koju treba najviše ulagati jer je ondje prinos po jedinici ulaganja najmanji [[26]](https://doi.org/10.1145/581271.581274). Ograničenje koje treba navesti uz svaku primjenu jest da model pretpostavlja neovisne i neadaptivne prijetnje [[26]](https://doi.org/10.1145/581271.581274). Uz strateškog protivnika vrijednost 1/e nije invarijantna [[32]](https://doi.org/10.1007/978-3-642-12586-7).

### 5.7. Zašto jedinstveni indeks nije obranjiv

Prva prepreka je nesumjerljivost jedinica, jer agregacija zahtijeva ili svođenje na jednu jedinicu ili priznanje da je riječ o višekriterijskom odlučivanju, a ne o mjerenju [[13]](https://doi.org/10.1016/0005-1098(78)90005-5). Druga je ordinalnost, zbog koje aritmetika nad rangovima nije dopuštena [[16]](https://doi.org/10.1126/science.103.2684.677). Treća je erozija pokazatelja pod upravljanjem, koja nije tehnički nego institucionalni problem i ne rješava se boljom formulom [[22]](https://doi.org/10.1016/0149-7189(79)90048-X). Jedina održiva obrana jest vektorski profil s Pareto-analizom, uz skalar samo ako je prethodno validiran prema vanjskom kriteriju [[19]](https://doi.org/10.1145/336512.336588).

### 5.8. Predloženi mjerni okvir

| Dimenzija | Pokazatelj | Izvor podatka | Referenca |
|---|---|---|---|
| Struktura | propagation cost, dubina dosezljivosti | statički graf ovisnosti | [[11]](https://doi.org/10.1016/j.respol.2012.04.011) |
| Sklad | NMI između strukturne particije i particije su-promjena | graf ovisnosti i povijest verzija | [[20]](https://doi.org/10.1088/1742-5468/2005/09/P09008) |
| Izloženost | mjera napadne površine | sučelja i povlastice | [[27]](https://doi.org/10.1109/TSE.2010.60) |
| Korelacija | udio modula s dijeljenim ovisnostima | popis sastavnica programske opreme | [[34]](https://nvd.nist.gov/vuln/detail/CVE-2021-44228) |
| Trenje | stopa zaobilaženja, broj koraka po zadatku | telemetrija i intervju | [[25]](https://doi.org/10.1145/1595676.1595684) |
| Radna točka | omjer lažno pozitivnih i lažno negativnih ishoda | zapisi kontrola | [[31]](https://doi.org/10.1109/TIT.1954.1057460) |
| Ekonomija | očekivani gubitak i omjer ulaganja prema stropu | procjena | [[26]](https://doi.org/10.1145/581271.581274) |

Odluka se pritom ne izriče kao jedan postotak, nego kao par vrijednosti: koliko pada očekivani gubitak i koliko raste trenje [S]. Izbor točke na Pareto-fronti time ostaje eksplicitna vrijednosna odluka, što je poštenije nego je sakriti u ponder [[19]](https://doi.org/10.1145/336512.336588).

### 5.9. Razilaženje okvira kao mjerljiv podatak

Simonov i Parnasov kriterij ne traže različitu mjeru, nego istu mjeru na dva različita grafa [S]. Visok stupanj poklapanja particija znači da struktura prati promjenu i da se oba kriterija slažu [[20]](https://doi.org/10.1088/1742-5468/2005/09/P09008). Nizak stupanj poklapanja upućuje na arhitektonski nesklad, jer je kod razdijeljen po jednom načelu, a mijenja se po drugom [[10]](https://doi.org/10.1109/TSE.2005.72). To je jedini pokazatelj iz cijelog skupa koji nosi informaciju koju nijedan pojedinačni pokazatelj ne nosi, jer mjeri odnos dvaju kriterija, a ne njihove razine [S]. Ujedno je i empirijski test polazne teze o segmentaciji radi razumljivosti nasuprot izolaciji promjene [[1]](https://doi.org/10.1145/361598.361623)[[5]](https://doi.org/10.1207/s15516709cog1202_4).

---

## 6. Zaključak

Mjera stanja i mjera odluke ne razlikuju se po težini izračuna nego po vrsti potrebnih ulaznih podataka, jer druga zahtijeva model budućnosti [[6]](https://mitpress.mit.edu/9780262024662/design-rules/). Njihova usporedba nije problem zajedničke skale nego problem ulančavanja, budući da strukturne mjere ulaze kao množitelj u ekonomske izraze [[11]](https://doi.org/10.1016/j.respol.2012.04.011)[[26]](https://doi.org/10.1145/581271.581274). Izražavanje u postocima obranjivo je samo za tri veličine: propagation cost [[11]](https://doi.org/10.1016/j.respol.2012.04.011), poklapanje particija [[20]](https://doi.org/10.1088/1742-5468/2005/09/P09008) i Gordon–Loebov strop ulaganja [[26]](https://doi.org/10.1145/581271.581274). Pojam volatilnosti mora se razdvojiti prije upotrebe, jer strateška komponenta ruši pretpostavke opcijskih modela [[32]](https://doi.org/10.1007/978-3-642-12586-7). Sukob sigurnosti i udobnosti mjerljiv je kao izbor radne točke klasifikatora, uz osnovnu stopu kao glavni izvor praktične erozije kontrola [[31]](https://doi.org/10.1109/TIT.1954.1057460)[[24]](https://doi.org/10.1145/322796.322806). Dekompozicija istodobno smanjuje domet proboja [[23]](https://doi.org/10.1109/PROC.1975.9939) i povećava izloženu površinu [[27]](https://doi.org/10.1109/TSE.2010.60), pa je optimum unutarnji, kao i kod kriterija minimalne duljine opisa [[13]](https://doi.org/10.1016/0005-1098(78)90005-5). Jedinstveni skalarni indeks nije formalno obranjiv, pa se predlaže vektorski profil sa sedam dimenzija i Pareto-analizom [[19]](https://doi.org/10.1145/336512.336588). Preostaje nemjerljiva jezgra, jer se esencijalna složenost granicama premješta, a ne uklanja [[29]](https://doi.org/10.1109/MC.1987.1663532)[[30]](http://pespmc1.vub.ac.be/books/IntroCyb.pdf).

**Preporučeni sljedeći korak** jest provesti jednu stvarnu granicu kroz oba računa, očekivani trošak promjene i očekivani gubitak, te usporediti rezultate [S]. Razilaženje dvaju izračuna bilo bi informativnije od slaganja, jer bi pokazalo koji se kriterij zapravo služi [[1]](https://doi.org/10.1145/361598.361623)[[2]](https://www.jstor.org/stable/985254).

---

### Napomena o citiranju

Oznaka **[S]** označava rečenicu koja je autorska sinteza ili izvedeni zaključak bez izravnog vanjskog izvora, i kao takva nije potkrijepljena referencom [S]. Sve ostale rečenice nose brojčanu referencu koja upućuje na stavku u odjeljku Literatura [S].

---

## 7. Literatura

1. Parnas, D. L. (1972). *On the Criteria To Be Used in Decomposing Systems into Modules*. Communications of the ACM, 15(12), 1053–1058. https://doi.org/10.1145/361598.361623
2. Simon, H. A. (1962). *The Architecture of Complexity*. Proceedings of the American Philosophical Society, 106(6), 467–482. https://www.jstor.org/stable/985254
3. Stevens, W. P., Myers, G. J., & Constantine, L. L. (1974). *Structured Design*. IBM Systems Journal, 13(2), 115–139. https://doi.org/10.1147/sj.132.0115
4. Miller, G. A. (1956). *The Magical Number Seven, Plus or Minus Two*. Psychological Review, 63(2), 81–97. https://doi.org/10.1037/h0043158
5. Sweller, J. (1988). *Cognitive Load During Problem Solving*. Cognitive Science, 12(2), 257–285. https://doi.org/10.1207/s15516709cog1202_4
6. Baldwin, C. Y., & Clark, K. B. (2000). *Design Rules, Vol. 1: The Power of Modularity*. MIT Press. https://mitpress.mit.edu/9780262024662/design-rules/
7. Newman, M. E. J., & Girvan, M. (2004). *Finding and Evaluating Community Structure in Networks*. Physical Review E, 69, 026113. https://doi.org/10.1103/PhysRevE.69.026113
8. Fortunato, S., & Barthélemy, M. (2007). *Resolution Limit in Community Detection*. PNAS, 104(1), 36–41. https://doi.org/10.1073/pnas.0605965104
9. Gall, H., Hajek, K., & Jazayeri, M. (1998). *Detection of Logical Coupling Based on Product Release History*. ICSM 1998. https://doi.org/10.1109/ICSM.1998.738508
10. Zimmermann, T., Weißgerber, P., Diehl, S., & Zeller, A. (2005). *Mining Version Histories to Guide Software Changes*. IEEE TSE, 31(6), 429–445. https://doi.org/10.1109/TSE.2005.72
11. MacCormack, A., Baldwin, C., & Rusnak, J. (2012). *Exploring the Duality Between Product and Organizational Architectures: A Test of the "Mirroring" Hypothesis*. Research Policy, 41(8), 1309–1324. https://doi.org/10.1016/j.respol.2012.04.011
12. Allen, E. B., & Khoshgoftaar, T. M. (1999). *Measuring Coupling and Cohesion: An Information-Theory Approach*. METRICS 1999. https://doi.org/10.1109/METRIC.1999.809743
13. Rissanen, J. (1978). *Modeling by Shortest Data Description*. Automatica, 14(5), 465–471. https://doi.org/10.1016/0005-1098(78)90005-5
14. Cilibrasi, R., & Vitányi, P. M. B. (2005). *Clustering by Compression*. IEEE Transactions on Information Theory, 51(4), 1523–1545. https://doi.org/10.1109/TIT.2005.844059
15. Krantz, D. H., Luce, R. D., Suppes, P., & Tversky, A. (1971). *Foundations of Measurement, Vol. I*. Academic Press. https://openlibrary.org/isbn/9780124254015
16. Stevens, S. S. (1946). *On the Theory of Scales of Measurement*. Science, 103(2684), 677–680. https://doi.org/10.1126/science.103.2684.677
17. Weyuker, E. J. (1988). *Evaluating Software Complexity Measures*. IEEE TSE, 14(9), 1357–1365. https://doi.org/10.1109/32.4634
18. Briand, L. C., Morasca, S., & Basili, V. R. (1996). *Property-Based Software Engineering Measurement*. IEEE TSE, 22(1), 68–86. https://doi.org/10.1109/32.481535
19. Fenton, N. E., & Neil, M. (2000). *Software Metrics: Roadmap*. ICSE 2000 — Future of Software Engineering. https://doi.org/10.1145/336512.336588
20. Danon, L., Díaz-Guilera, A., Duch, J., & Arenas, A. (2005). *Comparing Community Structure Identification*. Journal of Statistical Mechanics, P09008. https://doi.org/10.1088/1742-5468/2005/09/P09008
21. Hubert, L., & Arabie, P. (1985). *Comparing Partitions*. Journal of Classification, 2, 193–218. https://doi.org/10.1007/BF01908075
22. Campbell, D. T. (1979). *Assessing the Impact of Planned Social Change*. Evaluation and Program Planning, 2(1), 67–90. https://doi.org/10.1016/0149-7189(79)90048-X
23. Saltzer, J. H., & Schroeder, M. D. (1975). *The Protection of Information in Computer Systems*. Proceedings of the IEEE, 63(9), 1278–1308. https://doi.org/10.1109/PROC.1975.9939
24. Adams, A., & Sasse, M. A. (1999). *Users Are Not the Enemy*. Communications of the ACM, 42(12), 40–46. https://doi.org/10.1145/322796.322806
25. Beautement, A., Sasse, M. A., & Wonham, M. (2008). *The Compliance Budget: Managing Security Behaviour in Organisations*. NSPW 2008, 47–58. https://doi.org/10.1145/1595676.1595684
26. Gordon, L. A., & Loeb, M. P. (2002). *The Economics of Information Security Investment*. ACM TISSEC, 5(4), 438–457. https://doi.org/10.1145/581271.581274
27. Manadhata, P. K., & Wing, J. M. (2011). *An Attack Surface Metric*. IEEE TSE, 37(3), 371–386. https://doi.org/10.1109/TSE.2010.60
28. Anderson, R. (2001). *Why Information Security Is Hard — An Economic Perspective*. ACSAC 2001. https://doi.org/10.1109/ACSAC.2001.991552
29. Brooks, F. P. (1987). *No Silver Bullet: Essence and Accidents of Software Engineering*. IEEE Computer, 20(4), 10–19. https://doi.org/10.1109/MC.1987.1663532
30. Ashby, W. R. (1956). *An Introduction to Cybernetics*. Chapman & Hall. http://pespmc1.vub.ac.be/books/IntroCyb.pdf
31. Peterson, W. W., Birdsall, T. G., & Fox, W. C. (1954). *The Theory of Signal Detectability*. IRE Transactions on Information Theory, 4(4), 171–212. https://doi.org/10.1109/TIT.1954.1057460
32. von Stackelberg, H. (2011). *Market Structure and Equilibrium* (prijevod izvornika iz 1934.). Springer. https://doi.org/10.1007/978-3-642-12586-7
33. Siegmund, J., Kästner, C., Apel, S., Parnin, C., Bethmann, A., Leich, T., Saake, G., & Brechmann, A. (2014). *Understanding Understanding Source Code with Functional Magnetic Resonance Imaging*. ICSE 2014, 378–389. https://doi.org/10.1145/2568225.2568252
34. NIST National Vulnerability Database. *CVE-2021-44228 (Log4Shell)*. https://nvd.nist.gov/vuln/detail/CVE-2021-44228
