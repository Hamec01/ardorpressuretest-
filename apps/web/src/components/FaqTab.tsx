import React, { useState } from 'react';
import { useI18n } from '../context/LanguageContext';
import {
  HelpCircle,
  Search,
  UploadCloud,
  FileSpreadsheet,
  ShieldCheck,
  ChevronDown,
  ChevronUp,
  Terminal
} from 'lucide-react';

interface FaqItem {
  id: string;
  category: string;
  icon: any;
  title: Record<'en' | 'fi' | 'ru', string>;
  content: Record<'en' | 'fi' | 'ru', React.ReactNode>;
}

export const FaqTab: React.FC = () => {
  const { lang, t } = useI18n();
  const [search, setSearch] = useState<string>('');
  const [activeCategory, setActiveCategory] = useState<string>('all');
  const [openItems, setOpenItems] = useState<Record<string, boolean>>({
    'upload_package': true,
    'ptr_blank': true,
  });

  const toggleItem = (id: string) => {
    setOpenItems((prev) => ({ ...prev, [id]: !prev[id] }));
  };

  const faqItems: FaqItem[] = [
    {
      id: 'upload_package',
      category: 'upload',
      icon: UploadCloud,
      title: {
        en: 'How to upload WIKA CPG1500 logs (ZIP package, folder, or CSV)?',
        fi: 'Miten ladataan WIKA CPG1500 -lokit (ZIP-paketti, kansio tai CSV)?',
        ru: 'Как загружать логи опрессовки WIKA CPG1500 (ZIP архив, папка или CSV)?',
      },
      content: {
        en: (
          <div style={{ display: 'flex', flexDirection: 'column', gap: '0.6rem', fontSize: '0.9rem', lineHeight: 1.6 }}>
            <p>You can upload pressure tests to the system in 2 ways:</p>
            <ol style={{ paddingLeft: '1.2rem', display: 'flex', flexDirection: 'column', gap: '0.4rem' }}>
              <li>
                <strong>📦 ZIP package or whole folder:</strong> Click <code>+ New Test</code>, select the <em>"📦 Upload ZIP or Folder"</em> tab, and drop your ZIP archive or folder containing the CSV log, gauge photo, and pipe photos.
              </li>
              <li>
                <strong>📄 Single CSV form:</strong> Select the <em>"📄 Single CSV Form"</em> tab, upload the CSV file, and paste pipe numbers in the <code>Bundle/Pipe</code> format (e.g. <code>122153/41</code>).
              </li>
            </ol>
            <p style={{ color: 'var(--accent-emerald)', fontSize: '0.85rem' }}>
              ✓ The system automatically calculates SHA-256 integrity hashes, extracts pressure measurements, detects hold duration, and builds the 0–160 bar graph.
            </p>
          </div>
        ),
        fi: (
          <div style={{ display: 'flex', flexDirection: 'column', gap: '0.6rem', fontSize: '0.9rem', lineHeight: 1.6 }}>
            <p>Voit ladata painekokeita järjestelmään kahdella tavalla:</p>
            <ol style={{ paddingLeft: '1.2rem', display: 'flex', flexDirection: 'column', gap: '0.4rem' }}>
              <li>
                <strong>📦 ZIP-paketti tai koko kansio:</strong> Napsauta <code>+ Uusi koe</code>, valitse välilehti <em>"📦 Lataa ZIP tai kansio"</em> ja pudota ZIP-arkisto tai kansio, joka sisältää CSV-lokin ja valokuvat.
              </li>
              <li>
                <strong>📄 Yksittäinen CSV-lomake:</strong> Valitse välilehti <em>"📄 Yksittäinen CSV"</em>, lataa CSV-tiedosto ja syötä putkinumerot muodossa <code>Nippu/Putki</code> (esim. <code>122153/41</code>).
              </li>
            </ol>
            <p style={{ color: 'var(--accent-emerald)', fontSize: '0.85rem' }}>
              ✓ Järjestelmä laskee automaattisesti SHA-256-tarkistussummat, analysoi painearvot ja piirtää 0–160 bar -kuvaajan.
            </p>
          </div>
        ),
        ru: (
          <div style={{ display: 'flex', flexDirection: 'column', gap: '0.6rem', fontSize: '0.9rem', lineHeight: 1.6 }}>
            <p>Вы можете загрузить результаты опрессовки двумя удобными способами:</p>
            <ol style={{ paddingLeft: '1.2rem', display: 'flex', flexDirection: 'column', gap: '0.4rem' }}>
              <li>
                <strong>📦 Загрузка целой папки или ZIP-архива:</strong> Нажмите кнопку <code>+ Загрузить лог</code>, перейдите на вкладку <em>"📦 Загрузить ZIP или папку"</em> и перетащите архив/папку с CSV-файлом и фотографиями манометра и трубы.
              </li>
              <li>
                <strong>📄 Одиночный CSV файл:</strong> Выберите вкладку <em>"📄 Одиночный CSV"</em>, прикрепите файл и вставьте номера труб в формате <code>Связка/Труба</code> (например, <code>122153/41</code>).
              </li>
            </ol>
            <p style={{ color: 'var(--accent-emerald)', fontSize: '0.85rem' }}>
              ✓ Система автоматически проверяет контрольную сумму SHA-256, вычисляет выдержку давления и строит интерактивный график 0–160 bar.
            </p>
          </div>
        ),
      },
    },
    {
      id: 'ptr_blank',
      category: 'ptr',
      icon: FileSpreadsheet,
      title: {
        en: 'What is a Pressure Test Record (PTR) and how to create an official ARDOR blank?',
        fi: 'Mikä on Painekoepöytäkirja (PTR) ja miten luodaan virallinen ARDOR-lomake?',
        ru: 'Что такое Pressure Test Record (PTR) и как создать официальный бланк ARDOR?',
      },
      content: {
        en: (
          <div style={{ display: 'flex', flexDirection: 'column', gap: '0.6rem', fontSize: '0.9rem', lineHeight: 1.6 }}>
            <p>
              <strong>Pressure Test Record (PAINEKOEPÖYTÄKIRJA)</strong> is the official summary engineering document for clients and classification societies (DNV, Meyer Turku, etc.):
            </p>
            <ul style={{ paddingLeft: '1.2rem', display: 'flex', flexDirection: 'column', gap: '0.35rem' }}>
              <li>Includes Job No (<code>NB402</code>), Project Name, Inspection No, Design & Test Pressure.</li>
              <li>Contains a table of all tested pipes, drawings (<code>Piirustus nro</code>), and systems (<code>Systeemi</code>).</li>
              <li>Features official ARDOR branding, test medium checkboxes (Air / Water / Glycol / Nitrogen).</li>
              <li>Can be previewed live in the browser and downloaded with 1 click.</li>
            </ul>
            <p>To create one: Go to the <strong>Pressure Test Records</strong> tab $\rightarrow$ click <strong>+ Create Record</strong> $\rightarrow$ fill in parameters $\rightarrow$ click <strong>Save & Generate Official Blank</strong>.</p>
          </div>
        ),
        fi: (
          <div style={{ display: 'flex', flexDirection: 'column', gap: '0.6rem', fontSize: '0.9rem', lineHeight: 1.6 }}>
            <p>
              <strong>Painekoepöytäkirja (PAINEKOEPÖYTÄKIRJA / PRESSURE TEST RECORD)</strong> on virallinen laatudokumentti tilaajalle ja luokituslaitoksille (DNV, Meyer Turku):
            </p>
            <ul style={{ paddingLeft: '1.2rem', display: 'flex', flexDirection: 'column', gap: '0.35rem' }}>
              <li>Sisältää työnumeron (<code>NB402</code>), projektin nimen, tarkastusnumeron sekä suunnittelu- ja koepaineet.</li>
              <li>Sisältää taulukon testatuista putkista, piirustuksista (<code>Piirustus nro</code>) ja järjestelmistä (<code>Systeemi</code>).</li>
              <li>Sisältää virallisen ARDOR-logon ja testiainevalinnat (Vesi / Ilma / Glykoli / Typpi).</li>
              <li>Voidaan esikatsella reaaliaikaisesti verkkosivulla ja ladata PDF-muodossa.</li>
            </ul>
            <p>Luominen: Siirry <strong>Painekoepöytäkirjat</strong> -välilehdelle $\rightarrow$ napsauta <strong>+ Luo pöytäkirja</strong> $\rightarrow$ täytä tiedot $\rightarrow$ napsauta <strong>Tallenna & Muodosta virallinen lomake</strong>.</p>
          </div>
        ),
        ru: (
          <div style={{ display: 'flex', flexDirection: 'column', gap: '0.6rem', fontSize: '0.9rem', lineHeight: 1.6 }}>
            <p>
              <strong>Pressure Test Record (PAINEKOEPÖYTÄKIRJA)</strong> — это официальный сводный протокол опрессовки для заказчика и технадзора (DNV, Meyer Turku и др.):
            </p>
            <ul style={{ paddingLeft: '1.2rem', display: 'flex', flexDirection: 'column', gap: '0.35rem' }}>
              <li>Включает номер заказа (<code>NB402</code>), проект, номер инспекции, расчетное и испытательное давление.</li>
              <li>Содержит таблицу всех проверенных труб, чертежей (<code>Piirustus nro</code>) и систем (<code>Systeemi</code>).</li>
              <li>Оформлен по утверждённому финско-английскому стандарту ARDOR с оригинальным логотипом.</li>
              <li>Просматривается прямо на сайте во встроенном окне без необходимости скачивания.</li>
            </ul>
            <p>Как создать: Вкладка <strong>Протоколы ARDOR (PTR)</strong> $\rightarrow$ кнопка <strong>+ Создать протокол</strong> $\rightarrow$ заполните параметры $\rightarrow$ нажмите <strong>Сформировать официальный бланк</strong>.</p>
          </div>
        ),
      },
    },
    {
      id: 'digital_signature',
      category: 'signature',
      icon: ShieldCheck,
      title: {
        en: 'How to sign a document electronically and apply the Digital Verification Seal?',
        fi: 'Miten allekirjoittaa pöytäkirja sähköisesti ja lisätä digitaalinen varmennusleima?',
        ru: 'Как поставить электронную роспись и наложить цифровой защитный штамп?',
      },
      content: {
        en: (
          <div style={{ display: 'flex', flexDirection: 'column', gap: '0.6rem', fontSize: '0.9rem', lineHeight: 1.6 }}>
            <p>Foremen and inspectors can legally sign and verify documents directly on the website:</p>
            <ol style={{ paddingLeft: '1.2rem', display: 'flex', flexDirection: 'column', gap: '0.4rem' }}>
              <li>Open any Draft record in the <strong>Pressure Test Records</strong> tab.</li>
              <li>Click <strong>🔏 Draw Signature</strong> to draw your signature on the screen or touchscreen tablet.</li>
              <li>Click <strong>Seal & Verify</strong> to finalize the document. The system calculates a cryptographic SHA-256 hash and assigns a unique verification code (e.g. <code>ARDOR-VRF-4820-2026</code>).</li>
              <li>The PDF document instantly embeds the signature and green digital seal stamp, locking the document as an immutable record.</li>
            </ol>
          </div>
        ),
        fi: (
          <div style={{ display: 'flex', flexDirection: 'column', gap: '0.6rem', fontSize: '0.9rem', lineHeight: 1.6 }}>
            <p>Työnjohtajat ja tarkastajat voivat allekirjoittaa ja vahvistaa asiakirjat suoraan verkkosivulla:</p>
            <ol style={{ paddingLeft: '1.2rem', display: 'flex', flexDirection: 'column', gap: '0.4rem' }}>
              <li>Avaa luonnostilassa oleva pöytäkirja <strong>Painekoepöytäkirjat</strong> -välilehdellä.</li>
              <li>Napsauta <strong>🔏 Piirrä allekirjoitus</strong> piirtääksesi allekirjoituksen hiirellä tai kosketusnäytöllä.</li>
              <li>Napsauta <strong>Vahvista leimalla</strong>. Järjestelmä laskee SHA-256-tiivisteen ja luo yksilöllisen varmennuskoodin (esim. <code>ARDOR-VRF-4820-2026</code>).</li>
              <li>PDF-asiakirjaan lisätään automaattisesti allekirjoitus ja vihreä digitaalinen varmennusleima.</li>
            </ol>
          </div>
        ),
        ru: (
          <div style={{ display: 'flex', flexDirection: 'column', gap: '0.6rem', fontSize: '0.9rem', lineHeight: 1.6 }}>
            <p>Прорабы и инспекторы качества могут юридически заверять протоколы прямо на сайте:</p>
            <ol style={{ paddingLeft: '1.2rem', display: 'flex', flexDirection: 'column', gap: '0.4rem' }}>
              <li>Откройте любой черновик протокола во вкладке <strong>Протоколы ARDOR (PTR)</strong>.</li>
              <li>Нажмите <strong>🔏 Нарисовать роспись</strong> и распишитесь на экране (мышкой или пальцем на планшете).</li>
              <li>Нажмите <strong>Заверить штампом</strong>. Система сгенерирует криптографический SHA-256 хеш и присвоит код верификации (например, <code>ARDOR-VRF-4820-2026</code>).</li>
              <li>PDF-документ сразу же получает статус <code>CONFIRMED</code>, а в бланк впечатывается ваша роспись и зелёный защитный штамп!</li>
            </ol>
          </div>
        ),
      },
    },
    {
      id: 'search_filters',
      category: 'search',
      icon: Search,
      title: {
        en: 'How to search and switch between Grid Cards and Table View?',
        fi: 'Miten hakea kokeita ja vaihtaa kortti- ja taulukkonäkymän välillä?',
        ru: 'Как искать испытания и переключаться между Карточками и Таблицей?',
      },
      content: {
        en: (
          <div style={{ display: 'flex', flexDirection: 'column', gap: '0.6rem', fontSize: '0.9rem', lineHeight: 1.6 }}>
            <p>
              Use the unified search bar at the top of the <strong>Pressure Tests</strong> tab. The search is instant and queries:
            </p>
            <ul style={{ paddingLeft: '1.2rem', display: 'flex', flexDirection: 'column', gap: '0.35rem' }}>
              <li><strong>Log Number:</strong> e.g. <code>014FED</code> or <code>Log_014FED</code></li>
              <li><strong>Pipe or Bundle:</strong> e.g. <code>122153/41</code> or <code>122153</code></li>
              <li><strong>Operator or Project:</strong> e.g. <code>Matti</code> or <code>ICON3</code></li>
            </ul>
            <p>
              To switch display mode, click the <strong>🔲 Cards</strong> or <strong>📋 Table</strong> buttons on the right side of the filter bar for compact high-density list view.
            </p>
          </div>
        ),
        fi: (
          <div style={{ display: 'flex', flexDirection: 'column', gap: '0.6rem', fontSize: '0.9rem', lineHeight: 1.6 }}>
            <p>
              Käytä hakupalkkia <strong>Painekokeet</strong> -välilehdellä. Haku etsii reaaliaikaisesti:
            </p>
            <ul style={{ paddingLeft: '1.2rem', display: 'flex', flexDirection: 'column', gap: '0.35rem' }}>
              <li><strong>Lokinumero:</strong> esim. <code>014FED</code></li>
              <li><strong>Putki tai nippu:</strong> esim. <code>122153/41</code> tai <code>122153</code></li>
              <li><strong>Testaaja tai projekti:</strong> esim. <code>Matti</code> tai <code>ICON3</code></li>
            </ul>
            <p>
              Vaihda näkymää napsauttamalla suodatinpalkin oikeassa reunassa olevia painikkeita: <strong>🔲 Kortit</strong> tai <strong>📋 Taulukko</strong>.
            </p>
          </div>
        ),
        ru: (
          <div style={{ display: 'flex', flexDirection: 'column', gap: '0.6rem', fontSize: '0.9rem', lineHeight: 1.6 }}>
            <p>
              Используйте строку поиска во вкладке <strong>Логи опрессовки</strong>. Поиск работает мгновенно и ищет по:
            </p>
            <ul style={{ paddingLeft: '1.2rem', display: 'flex', flexDirection: 'column', gap: '0.35rem' }}>
              <li><strong>Номеру лога:</strong> например <code>014FED</code>;</li>
              <li><strong>Номеру трубы или связки:</strong> например <code>122153/41</code> или <code>122153</code>;</li>
              <li><strong>Оператору или проекту:</strong> например <code>Matti</code> или <code>ARDOR</code>.</li>
            </ul>
            <p>
              Справа от фильтров находятся кнопки переключения вида: <strong>🔲 Карточки</strong> (с графиками и миниатюрами фото) или <strong>📋 Таблица</strong> (компактный индустриальный список).
            </p>
          </div>
        ),
      },
    },
    {
      id: 'offline_desktop',
      category: 'desktop',
      icon: Terminal,
      title: {
        en: 'Offline work on site & standalone Desktop EXE application',
        fi: 'Offline-työskentely työmaalla & itsenäinen Desktop EXE -sovellus',
        ru: 'Автономная работа на объекте и Desktop EXE приложение',
      },
      content: {
        en: (
          <div style={{ display: 'flex', flexDirection: 'column', gap: '0.6rem', fontSize: '0.9rem', lineHeight: 1.6 }}>
            <p>
              On construction sites without reliable internet connection, inspectors and operators can use the standalone Windows desktop application:
            </p>
            <ul style={{ paddingLeft: '1.2rem', display: 'flex', flexDirection: 'column', gap: '0.35rem' }}>
              <li>Located at <code>dist/WIKA CPG1500 Processor.exe</code> (portable, no installation required).</li>
              <li>Processes CSV files, builds graphs and Excel sheets locally into the <code>testlogs/</code> folder.</li>
              <li>Queues tests for automatic 1-click synchronization to the central server when back online.</li>
            </ul>
          </div>
        ),
        fi: (
          <div style={{ display: 'flex', flexDirection: 'column', gap: '0.6rem', fontSize: '0.9rem', lineHeight: 1.6 }}>
            <p>
              Työmailla, joissa ei ole verkkoyhteyttä, voidaan käyttää itsenäistä Windows-työpöytäsovellusta:
            </p>
            <ul style={{ paddingLeft: '1.2rem', display: 'flex', flexDirection: 'column', gap: '0.35rem' }}>
              <li>Sijaitsee kansiossa <code>dist/WIKA CPG1500 Processor.exe</code> (ei vaadi asennusta).</li>
              <li>Käsittelee CSV-tiedostot, piirtää kuvaajat ja luo Excel-raportit paikalliseen <code>testlogs/</code> -kansioon.</li>
              <li>Synkronoi kokeet automaattisesti palvelimelle verkkoyhteyden palauduttua.</li>
            </ul>
          </div>
        ),
        ru: (
          <div style={{ display: 'flex', flexDirection: 'column', gap: '0.6rem', fontSize: '0.9rem', lineHeight: 1.6 }}>
            <p>
              На строительных объектах без доступа к интернету операторы могут использовать автономное Windows-приложение:
            </p>
            <ul style={{ paddingLeft: '1.2rem', display: 'flex', flexDirection: 'column', gap: '0.35rem' }}>
              <li>Файл <code>dist/WIKA CPG1500 Processor.exe</code> (портативный, не требует установки).</li>
              <li>Обрабатывает CSV-логи манометра WIKA, строит графики и генерирует Excel-отчеты локально на диске.</li>
              <li>Автоматически ставит файлы в очередь синхронизации и отправляет на сервер при появлении сети.</li>
            </ul>
          </div>
        ),
      },
    },
  ];

  const filteredItems = faqItems.filter((item) => {
    const titleText = item.title[lang] || item.title.en;
    const matchesSearch = !search || titleText.toLowerCase().includes(search.toLowerCase());
    const matchesCat = activeCategory === 'all' || item.category === activeCategory;
    return matchesSearch && matchesCat;
  });

  return (
    <div style={{ maxWidth: '960px', margin: '0 auto', display: 'flex', flexDirection: 'column', gap: '1.5rem' }}>
      {/* Top Banner */}
      <div style={{ background: 'rgba(30, 58, 138, 0.12)', border: '1px solid rgba(59, 130, 246, 0.3)', borderRadius: 'var(--radius-md)', padding: '1.25rem 1.5rem', display: 'flex', alignItems: 'center', gap: '1rem' }}>
        <div style={{ width: '48px', height: '48px', borderRadius: 'var(--radius-md)', background: 'rgba(59, 130, 246, 0.2)', display: 'flex', alignItems: 'center', justifyContent: 'center', flexShrink: 0 }}>
          <HelpCircle size={28} color="var(--accent-cyan)" />
        </div>
        <div>
          <h2 style={{ fontSize: '1.25rem', fontWeight: 700, color: 'var(--text-primary)', marginBottom: '0.2rem' }}>
            {t('faq_title')}
          </h2>
          <p style={{ fontSize: '0.85rem', color: 'var(--text-secondary)', lineHeight: 1.4 }}>
            {t('faq_subtitle')}
          </p>
        </div>
      </div>

      {/* Search Bar */}
      <div className="search-input-wrapper">
        <Search size={18} className="search-icon" />
        <input
          type="text"
          className="search-input"
          placeholder={t('faq_search')}
          value={search}
          onChange={(e) => setSearch(e.target.value)}
        />
      </div>

      {/* Category Pills */}
      <div className="filter-pills" style={{ marginTop: '-0.5rem' }}>
        <button className={`filter-pill ${activeCategory === 'all' ? 'active' : ''}`} onClick={() => setActiveCategory('all')}>
          {lang === 'fi' ? 'Kaikki aiheet' : lang === 'ru' ? 'Все темы' : 'All Topics'}
        </button>
        <button className={`filter-pill ${activeCategory === 'upload' ? 'active' : ''}`} onClick={() => setActiveCategory('upload')}>
          {lang === 'fi' ? '📦 Lokien lataus' : lang === 'ru' ? '📦 Загрузка логов' : '📦 Uploading Logs'}
        </button>
        <button className={`filter-pill ${activeCategory === 'ptr' ? 'active' : ''}`} onClick={() => setActiveCategory('ptr')}>
          {lang === 'fi' ? '📋 Pöytäkirjat (PTR)' : lang === 'ru' ? '📋 Протоколы (PTR)' : '📋 PTR Blanks'}
        </button>
        <button className={`filter-pill ${activeCategory === 'signature' ? 'active' : ''}`} onClick={() => setActiveCategory('signature')}>
          {lang === 'fi' ? '🔏 Allekirjoitus & Leima' : lang === 'ru' ? '🔏 Подпись и Штамп' : '🔏 Verification'}
        </button>
        <button className={`filter-pill ${activeCategory === 'search' ? 'active' : ''}`} onClick={() => setActiveCategory('search')}>
          {lang === 'fi' ? '🔍 Haku & Taulukko' : lang === 'ru' ? '🔍 Поиск и Таблица' : '🔍 Search & Table'}
        </button>
      </div>

      {/* FAQ Accordion List */}
      <div style={{ display: 'flex', flexDirection: 'column', gap: '0.85rem' }}>
        {filteredItems.map((item) => {
          const isOpen = !!openItems[item.id];
          const IconComp = item.icon;
          return (
            <div
              key={item.id}
              style={{
                background: 'rgba(15, 23, 42, 0.65)',
                border: isOpen ? '1px solid var(--accent-cyan)' : '1px solid var(--border-color)',
                borderRadius: 'var(--radius-md)',
                overflow: 'hidden',
                transition: 'all 0.2s ease',
              }}
            >
              <button
                type="button"
                onClick={() => toggleItem(item.id)}
                style={{
                  width: '100%',
                  padding: '1rem 1.25rem',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'space-between',
                  gap: '1rem',
                  background: 'transparent',
                  border: 'none',
                  color: 'inherit',
                  cursor: 'pointer',
                  textAlign: 'left',
                }}
              >
                <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem' }}>
                  <div style={{ width: '32px', height: '32px', borderRadius: 'var(--radius-sm)', background: 'rgba(56, 189, 248, 0.12)', display: 'flex', alignItems: 'center', justifyContent: 'center', flexShrink: 0 }}>
                    <IconComp size={18} color="var(--accent-cyan)" />
                  </div>
                  <span style={{ fontSize: '0.95rem', fontWeight: 600, color: 'var(--text-primary)' }}>
                    {item.title[lang] || item.title.en}
                  </span>
                </div>

                {isOpen ? <ChevronUp size={18} color="var(--accent-cyan)" /> : <ChevronDown size={18} color="var(--text-muted)" />}
              </button>

              {isOpen && (
                <div
                  style={{
                    padding: '0 1.25rem 1.25rem 3.5rem',
                    borderTop: '1px solid rgba(148, 163, 184, 0.08)',
                    paddingTop: '0.85rem',
                    color: 'var(--text-secondary)',
                  }}
                >
                  {item.content[lang] || item.content.en}
                </div>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
};
