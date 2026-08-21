import React, { useState } from 'react';
import { useI18n } from '../context/LanguageContext';
import {
  HelpCircle,
  Search,
  UploadCloud,
  ShieldCheck,
  ChevronDown,
  ChevronUp,
  Terminal,
  Cloud,
  Layers,
  Camera,
  Trash2
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
    'composite_ptr': true,
    'pipecloud_status': true,
    'upload_package': false,
  });

  const toggleItem = (id: string) => {
    setOpenItems((prev) => ({ ...prev, [id]: !prev[id] }));
  };

  const faqItems: FaqItem[] = [
    {
      id: 'composite_ptr',
      category: 'ptr',
      icon: Layers,
      title: {
        en: 'How does the Composite Pressure Test Record (Official Blank + Full PDF) work?',
        fi: 'Miten yhdistetty Painekoepöytäkirja (Virallinen lomake + Full PDF) toimii?',
        ru: 'Как работает составной протокол (Официальный бланк ARDOR + Полный Full Composite PDF)?',
      },
      content: {
        en: (
          <div style={{ display: 'flex', flexDirection: 'column', gap: '0.6rem', fontSize: '0.9rem', lineHeight: 1.6 }}>
            <p>
              The system allows creating comprehensive multi-log quality packages according to ARDOR standards:
            </p>
            <ol style={{ paddingLeft: '1.2rem', display: 'flex', flexDirection: 'column', gap: '0.4rem' }}>
              <li>
                <strong>Official ARDOR Blank (Official PDF):</strong> Multi-page vector form containing the pipe specification (supports 30–40+ pipes across pages with repeated headers), design parameters, and digital verification seal.
              </li>
              <li>
                <strong>Full Composite PDF:</strong> A single consolidated engineering package combining:
                <ul style={{ paddingLeft: '1.2rem', marginTop: '0.3rem' }}>
                  <li>All pages of the Official ARDOR Record;</li>
                  <li>Sequential Log Sections (Log summary, pressure graph, attached photos);</li>
                  <li>Optional complete WIKA CPG1500 raw CSV measurement tables (~4 pages per log without downsampling).</li>
                </ul>
              </li>
              <li>
                <strong>Interactive Builder:</strong> In the <code>+ Create PTR</code> modal, click <code>+ Add Pressure Test Log</code> to search and attach logs, toggle measurement tables, reorder sections with (↑/↓), and view live page count estimation.
              </li>
            </ol>
            <p style={{ color: 'var(--accent-cyan)', fontSize: '0.85rem' }}>
              ✓ Both the Official Blank and Full Composite PDF compute cryptographic SHA-256 byte hashes upon confirmation.
            </p>
          </div>
        ),
        fi: (
          <div style={{ display: 'flex', flexDirection: 'column', gap: '0.6rem', fontSize: '0.9rem', lineHeight: 1.6 }}>
            <p>
              Järjestelmä mahdollistaa useiden lokien yhdistämisen viralliseksi ARDOR-laatuasiakirjaksi:
            </p>
            <ol style={{ paddingLeft: '1.2rem', display: 'flex', flexDirection: 'column', gap: '0.4rem' }}>
              <li>
                <strong>Virallinen ARDOR-lomake (Official PDF):</strong> Monisivuinen vektorilomake, joka sisältää putkilistan (tukee 30–40+ putkea sivutuksella ja toistuvilla otsikoilla), suunnittelupaineet ja digitaalisen varmennusleiman.
              </li>
              <li>
                <strong>Täydellinen koontitiedosto (Full Composite PDF):</strong> Yhdistää yhteen PDF-tiedostoon:
                <ul style={{ paddingLeft: '1.2rem', marginTop: '0.3rem' }}>
                  <li>Kaikki virallisen ARDOR-pöytäkirjan sivut;</li>
                  <li>Jokaisen liitetyn lokin osiot (yhteenveto, painekuvan kuvaaja, valokuvat);</li>
                  <li>WIKA CPG1500 -mittauspistetaulukon (~4 sivua per loki ilman näytteenottoa).</li>
                </ul>
              </li>
              <li>
                <strong>Vuorovaikutteinen luontityökalu:</strong> <code>+ Luo pöytäkirja</code> -ikkunassa napsauta <code>+ Lisää koeloki</code> liittääksesi kokeita, valitaksesi valokuvia ja nähdäksesi arvioidun sivumäärän.
              </li>
            </ol>
          </div>
        ),
        ru: (
          <div style={{ display: 'flex', flexDirection: 'column', gap: '0.6rem', fontSize: '0.9rem', lineHeight: 1.6 }}>
            <p>
              Система позволяет формировать составные инженерные пакеты качества по стандартам ARDOR:
            </p>
            <ol style={{ paddingLeft: '1.2rem', display: 'flex', flexDirection: 'column', gap: '0.4rem' }}>
              <li>
                <strong>Официальный бланк ARDOR (Official PDF):</strong> Многостраничный векторный документ со спецификацией труб (поддерживает 30–40+ труб с переносом строк на следующие листы), параметрами испытания и защитным штампом.
              </li>
              <li>
                <strong>Полный составной пакет (Full Composite PDF):</strong> Единый файл, объединяющий:
                <ul style={{ paddingLeft: '1.2rem', marginTop: '0.3rem' }}>
                  <li>Все листы официального бланка ARDOR;</li>
                  <li>Разделы по каждому прикрепленному логу (сводка параметров, график 0–160 bar, отобранные фото манометра и труб);</li>
                  <li>Полную таблицу всех точек измерений WIKA CPG1500 из CSV (~4 стр. на лог без сэмплинга и потерь данных).</li>
                </ul>
              </li>
              <li>
                <strong>Конструктор протокола:</strong> В окне <code>+ Создать протокол</code> нажмите <code>+ Добавить лог испытания</code>, чтобы выбрать логи из базы, включить/отключить таблицы измерений, настроить фотографии и увидеть живую оценку количества страниц.
              </li>
            </ol>
            <p style={{ color: 'var(--accent-emerald)', fontSize: '0.85rem' }}>
              ✓ При подтверждении протокола рассчитываются два независимых SHA-256 хэша: для официального бланка и для полного PDF-пакета.
            </p>
          </div>
        ),
      },
    },
    {
      id: 'pipecloud_status',
      category: 'pipecloud',
      icon: Cloud,
      title: {
        en: 'What is the "Added to PipeCloud" status and how does it work?',
        fi: 'Mikä on "Lisätty PipeCloudiin" -tila ja miten se toimii?',
        ru: 'Что означает статус "Добавлено в PipeCloud" (PipeCloud Workflow)?',
      },
      content: {
        en: (
          <div style={{ display: 'flex', flexDirection: 'column', gap: '0.6rem', fontSize: '0.9rem', lineHeight: 1.6 }}>
            <p>
              <strong>Added to PipeCloud</strong> is a manual tracking indicator for production staff:
            </p>
            <ul style={{ paddingLeft: '1.2rem', display: 'flex', flexDirection: 'column', gap: '0.35rem' }}>
              <li>
                <strong>Manual control:</strong> Every new test starts with status <span style={{ color: 'var(--accent-rose)', fontWeight: 700 }}>PIPECLOUD: NOT ADDED</span>. It is never set or reset automatically.
              </li>
              <li>
                <strong>Independent workflow:</strong> Updating pipe lists, notes, or creating new test revisions does not reset the PipeCloud status.
              </li>
              <li>
                <strong>Quick toggle:</strong> Any authorized team member can toggle the status directly in the log card, table view, or modal window.
              </li>
              <li>
                <strong>Audit Trail:</strong> Every change logs the user name, timestamp, and previous status in the immutable Audit Log.
              </li>
              <li>
                <strong>Desktop sync:</strong> When working offline in the Windows Desktop app, status changes are queued and synced safely upon reconnecting.
              </li>
            </ul>
          </div>
        ),
        fi: (
          <div style={{ display: 'flex', flexDirection: 'column', gap: '0.6rem', fontSize: '0.9rem', lineHeight: 1.6 }}>
            <p>
              <strong>Lisätty PipeCloudiin (Added to PipeCloud)</strong> on manuaalinen työnkulun tila:
            </p>
            <ul style={{ paddingLeft: '1.2rem', display: 'flex', flexDirection: 'column', gap: '0.35rem' }}>
              <li>
                <strong>Manuaalinen ohjaus:</strong> Kaikki uudet kokeet luodaan tilassa <span style={{ color: 'var(--accent-rose)', fontWeight: 700 }}>PIPECLOUD: EI LISÄTTY</span>. Tilaa ei koskaan aseteta tai nollata automaattisesti.
              </li>
              <li>
                <strong>Itsenäisyys:</strong> Putkilistan, muistiinpanojen tai uusien revisioiden luominen ei muuta PipeCloud-tilaa.
              </li>
              <li>
                <strong>Nopea kytkentä:</strong> Kuka tahansa kirjautunut työntekijä voi vaihtaa tilan suoraan koekortilta tai taulukosta.
              </li>
              <li>
                <strong>Auditointi:</strong> Jokainen tilanmuutos tallentaa käyttäjän nimen, aikaleiman ja vanhan arvon tarkastuslokiin.
              </li>
            </ul>
          </div>
        ),
        ru: (
          <div style={{ display: 'flex', flexDirection: 'column', gap: '0.6rem', fontSize: '0.9rem', lineHeight: 1.6 }}>
            <p>
              <strong>Добавлено в PipeCloud (Added to PipeCloud)</strong> — это ручной индикатор учета для опрессовщиков и мастеров:
            </p>
            <ul style={{ paddingLeft: '1.2rem', display: 'flex', flexDirection: 'column', gap: '0.35rem' }}>
              <li>
                <strong>Полностью ручной контроль:</strong> Все новые испытания создаются со статусом <span style={{ color: 'var(--accent-rose)', fontWeight: 700 }}>PIPECLOUD: NOT ADDED</span> (красный бейдж). Статус никогда не выставляется и не сбрасывается программой автоматически.
              </li>
              <li>
                <strong>Независимость данных:</strong> Добавление новых ревизий, изменение номеров труб или редактирование заметок не сбрасывают отметку PipeCloud.
              </li>
              <li>
                <strong>Переключение в один клик:</strong> Любой авторизованный сотрудник может переключить тумблер прямо в карточке лога, в таблице или в окне просмотра.
              </li>
              <li>
                <strong>Журнал аудита:</strong> Каждое переключение фиксирует имя сотрудника, дату, время и источник действия в неизменяемом Audit Trail.
              </li>
              <li>
                <strong>Офлайн-синхронизация:</strong> В Windows EXE приложении переключение сохраняется в локальный sidecar-файл <code>pipecloud_status.txt</code> и отправляется на сервер через очередь синхронизации.
              </li>
            </ul>
          </div>
        ),
      },
    },
    {
      id: 'photos_and_evidence',
      category: 'upload',
      icon: Camera,
      title: {
        en: 'How to attach and manage gauge & pipe inspection photos?',
        fi: 'Miten liittää ja hallita painemittarin ja putkien valokuvia?',
        ru: 'Как прикреплять и просматривать фотографии манометра и труб?',
      },
      content: {
        en: (
          <div style={{ display: 'flex', flexDirection: 'column', gap: '0.6rem', fontSize: '0.9rem', lineHeight: 1.6 }}>
            <p>Inspection photos provide essential evidence for pressure tests:</p>
            <ol style={{ paddingLeft: '1.2rem', display: 'flex', flexDirection: 'column', gap: '0.4rem' }}>
              <li>
                <strong>Automatic Folder Import:</strong> When uploading a folder or ZIP package containing an <code>attached_photos/</code> directory or image files (<code>.jpg</code>, <code>.png</code>), the system automatically discovers and categorizes photos as Gauge (Манометр) or Pipe (Труба).
              </li>
              <li>
                <strong>Direct Web Attachment:</strong> Open any test log $\rightarrow$ in the <em>"Attached Photographs"</em> section click <code>📷 Attach Photos</code> to add photos directly from your computer or smartphone.
              </li>
              <li>
                <strong>Fullscreen Preview:</strong> Click on any photo thumbnail in the log details to open full-resolution inspection zoom.
              </li>
            </ol>
          </div>
        ),
        fi: (
          <div style={{ display: 'flex', flexDirection: 'column', gap: '0.6rem', fontSize: '0.9rem', lineHeight: 1.6 }}>
            <p>Tarkastusvalokuvat ovat olennainen osa koetodistusta:</p>
            <ol style={{ paddingLeft: '1.2rem', display: 'flex', flexDirection: 'column', gap: '0.4rem' }}>
              <li>
                <strong>Automaattinen kansion tuonti:</strong> Kun lataat kansion tai ZIP-paketin, järjestelmä tunnistaa automaattisesti <code>attached_photos/</code> -kansion kuvat ja luokittelee ne (Mittari / Putki).
              </li>
              <li>
                <strong>Suora lataus selaimessa:</strong> Avaa koe $\rightarrow$ napsauta <em>"Liitetyt valokuvat"</em> -kohdassa <code>📷 Liitä valokuvia</code> lisätäksesi kuvia milloin tahansa.
              </li>
              <li>
                <strong>Täysikokoinen esikatselu:</strong> Napsauta mitä tahansa pikkukuvaa avataksesi kuvan suurennuksen.
              </li>
            </ol>
          </div>
        ),
        ru: (
          <div style={{ display: 'flex', flexDirection: 'column', gap: '0.6rem', fontSize: '0.9rem', lineHeight: 1.6 }}>
            <p>Фотографии манометра и труб являются доказательной базой опрессовки:</p>
            <ol style={{ paddingLeft: '1.2rem', display: 'flex', flexDirection: 'column', gap: '0.4rem' }}>
              <li>
                <strong>Автоматическое обнаружение при загрузке папки:</strong> При загрузке папки или архива из Windows-приложения система автоматически находит все вложенные фотографии (в том числе в подпапке <code>attached_photos/</code>) и присваивает бейджи <em>«Манометр (Gauge)»</em> или <em>«Труба (Pipe)»</em>.
              </li>
              <li>
                <strong>Кнопка прямого прикрепления:</strong> В окне просмотра любого лога нажмите кнопку <code>📷 Прикрепить фото</code>, чтобы добавить фото манометра или труб прямо с телефона или компьютера.
              </li>
              <li>
                <strong>Просмотр во весь экран:</strong> Кликните на любую фотографию в галерее лога для открытия полноразмерного изображения.
              </li>
            </ol>
          </div>
        ),
      },
    },
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
      id: 'soft_deletion',
      category: 'ptr',
      icon: Trash2,
      title: {
        en: 'How does deletion work and are records stored permanently?',
        fi: 'Miten poistaminen toimii ja säilyvätkö tiedot pysyvästi?',
        ru: 'Как устроено удаление протоколов и логов (Soft Deletion & Audit Trail)?',
      },
      content: {
        en: (
          <div style={{ display: 'flex', flexDirection: 'column', gap: '0.6rem', fontSize: '0.9rem', lineHeight: 1.6 }}>
            <p>
              According to quality and traceability standards, data deletion is <strong>logical (Soft Delete)</strong>:
            </p>
            <ul style={{ paddingLeft: '1.2rem', display: 'flex', flexDirection: 'column', gap: '0.35rem' }}>
              <li>Deleted items are marked as <code>is_archived = True</code> and hidden from normal active views.</li>
              <li>Physical files, CSVs, photographs, and historical SHA-256 revision manifests are preserved in permanent storage.</li>
              <li>Every deletion action records the operator name, timestamp, and reason in the immutable Audit Trail.</li>
            </ul>
          </div>
        ),
        fi: (
          <div style={{ display: 'flex', flexDirection: 'column', gap: '0.6rem', fontSize: '0.9rem', lineHeight: 1.6 }}>
            <p>
              Laatu- ja jäljitettävyysvaatimusten mukaisesti poistaminen on <strong>loogista (Soft Delete)</strong>:
            </p>
            <ul style={{ paddingLeft: '1.2rem', display: 'flex', flexDirection: 'column', gap: '0.35rem' }}>
              <li>Poistetut kohteet merkitään arkistoiduiksi ja piilotetaan aktiivisesta näkymästä.</li>
              <li>Fyysiset tiedostot, CSV-lokit, valokuvat ja SHA-256-tarkistussummat säilytetään pysyvästi.</li>
              <li>Kaikki poistotapahtumat kirjataan tarkastuslokiin (Audit Trail).</li>
            </ul>
          </div>
        ),
        ru: (
          <div style={{ display: 'flex', flexDirection: 'column', gap: '0.6rem', fontSize: '0.9rem', lineHeight: 1.6 }}>
            <p>
              В соответствии с правилами постоянного хранения и стандартами качества удаление является <strong>логическим (Soft Delete)</strong>:
            </p>
            <ul style={{ paddingLeft: '1.2rem', display: 'flex', flexDirection: 'column', gap: '0.35rem' }}>
              <li>При нажатии на значок корзины сущность помечается как архивная (<code>is_archived = True</code>) и скрывается из основного рабочего списка.</li>
              <li>Исходные CSV-файлы, фотографии, сгенерированные графики и доказательные SHA-256 манифесты никогда не уничтожаются с диска.</li>
              <li>Каждое удаление фиксируется в Журнале аудита (Audit Trail) с указанием автора, времени и параметров объекта.</li>
            </ul>
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
              <li><strong>PipeCloud Filter:</strong> filter by <em>All / Added / Not Added</em> to find pending PipeCloud entries quickly.</li>
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
              <li><strong>PipeCloud-suodatin:</strong> suodata <em>Kaikki / Lisätty / Ei lisätty</em> löytääksesi kirjaamattomat kokeet nopeasti.</li>
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
              <li><strong>Оператору или проекту:</strong> например <code>Matti</code> или <code>ARDOR</code>;</li>
              <li><strong>Фильтру PipeCloud:</strong> переключатели <em>Все / Добавлено / Не добавлено</em> для мгновенного поиска не занесённых в PipeCloud логов.</li>
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
              <li>Supports offline PipeCloud toggle and queues changes for safe 1-click synchronization to the central server when back online.</li>
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
              <li>Tukee offline PipeCloud -kytkintä ja synkronoi kokeet palvelimelle verkkoyhteyden palauduttua.</li>
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
              <li>Поддерживает офлайн-тумблер PipeCloud и автоматически ставит изменения в очередь синхронизации.</li>
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
        <button className={`filter-pill ${activeCategory === 'ptr' ? 'active' : ''}`} onClick={() => setActiveCategory('ptr')}>
          {lang === 'fi' ? '📋 Pöytäkirjat (PTR & Full PDF)' : lang === 'ru' ? '📋 Составные PTR & Full PDF' : '📋 Composite PTR & PDF'}
        </button>
        <button className={`filter-pill ${activeCategory === 'pipecloud' ? 'active' : ''}`} onClick={() => setActiveCategory('pipecloud')}>
          {lang === 'fi' ? '☁️ PipeCloud-tila' : lang === 'ru' ? '☁️ Статус PipeCloud' : '☁️ PipeCloud Workflow'}
        </button>
        <button className={`filter-pill ${activeCategory === 'upload' ? 'active' : ''}`} onClick={() => setActiveCategory('upload')}>
          {lang === 'fi' ? '📦 Lokit & Valokuvat' : lang === 'ru' ? '📦 Загрузка и Фотографии' : '📦 Upload & Photos'}
        </button>
        <button className={`filter-pill ${activeCategory === 'signature' ? 'active' : ''}`} onClick={() => setActiveCategory('signature')}>
          {lang === 'fi' ? '🔏 Allekirjoitus & Leima' : lang === 'ru' ? '🔏 Подпись и Штамп' : '🔏 Verification'}
        </button>
        <button className={`filter-pill ${activeCategory === 'desktop' ? 'active' : ''}`} onClick={() => setActiveCategory('desktop')}>
          {lang === 'fi' ? '💻 Työpöytäsovellus' : lang === 'ru' ? '💻 Desktop EXE' : '💻 Desktop App'}
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
