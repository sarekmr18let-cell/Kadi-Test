/**
 * KADI Mini App i18n
 * Supported languages: Russian, English, Uzbek (Latin)
 */
(function () {
  const LANGS = ['ru', 'en', 'uz'];

  const dict = {
    ru: {
      app_title: 'KADI — магазин донатов',
      loading: 'ЗАГРУЗКА',
      home: 'Главная',
      catalog: 'Каталог',
      orders: 'Заказы',
      profile: 'Профиль',
      search_placeholder: 'Поиск игр, товаров, подарочных карт...',
      hero_title: 'Пополняй игры быстро',
      hero_subtitle: "",
      explore_now: 'Смотреть товары →',
      categories: 'Категории',
      see_all: 'Все →',
      popular_now: '🔥 Популярное',
      new: 'NEW',
      referral_program: 'Реферальная программа',
      referral_desc: 'Приглашай друзей и получай бонусы с покупок!',
      all: 'Все',
      back: 'Назад',
      back_to_cart: 'Назад в корзину',
      cart: 'Корзина',
      empty_cart: 'Корзина пустая',
      start_shopping: 'Начать покупки',
      subtotal: 'Сумма',
      discount: 'Скидка',
      total: 'Итого',
      checkout: 'Оформление',
      proceed_checkout: 'Перейти к оплате',
      account_details: '🎮 Данные аккаунта',
      target_label: 'User ID / Game ID / Telegram',
      target_placeholder: 'Введи ID или username',
      server_label: 'Сервер, если нужен',
      server_placeholder: 'Укажи сервер',
      promo_code: '🎟️ Промокод',
      promo_placeholder: 'Введи промокод',
      apply: 'Применить',
      wallet_balance: '💰 Баланс кошелька',
      paid_from_balance_hint: 'Заказ будет оплачен с твоего баланса.',
      available: 'Доступно:',
      topup_before_buying: 'Пополни баланс в профиле перед покупкой.',
      items: 'Товары',
      total_to_pay: 'К оплате',
      place_order: 'Создать заказ',
      pay_from_balance: 'Оплатить с баланса',
      insufficient_balance: 'Недостаточно баланса — сначала пополни',
      my_orders: 'Мои заказы',
      pending: 'Ожидание',
      checking: 'Проверка',
      paid: 'Оплачен',
      completed: 'Выполнен',
      balance: 'Баланс',
      spent: 'Потрачено',
      topup_balance: '💳 Пополнить баланс',
      topup_amount_placeholder: 'Сумма в UZS',
      get_card: 'Получить карту',
      support: 'Поддержка',
      admin_panel: 'Админ-панель',
      dashboard: 'Дашборд',
      products: 'Товары',
      users: 'Пользователи',
      p2p_topups: 'P2P / Пополнения',
      system_check: 'Проверка системы',
      total_users: 'Всего пользователей',
      total_orders: 'Всего заказов',
      total_revenue: 'Выручка',
      add_category: '+ Добавить категорию',
      add_product: '+ Добавить товар',
      refresh: 'Обновить',
      search_users: 'Поиск пользователей...',
      add_card: '+ Добавить карту',
      cards: 'Карты',
      topups_review: 'Пополнения / Проверка',
      run_check: 'Проверить',
      parse_humo_text: 'Разобрать HUMO текст',
      process_test_payment: 'Тест платежа',
      no_products: 'Товары не найдены',
      instant_delivery: 'Мгновенная цифровая доставка',
      select_amount: 'Выбери вариант',
      in_stock: '✓ В наличии',
      out_of_stock: '✗ Нет в наличии',
      add_to_cart: 'Добавить в корзину',
      qty: 'Кол-во',
      copied: 'Скопировано',
      copy_failed: 'Не удалось скопировать',
      no_active_payment_session: 'Нет активной платежной сессии',
      p2p_payment: '💳 P2P оплата',
      pay_exact_amount: 'Переведи точную сумму:',
      transfer_amount: 'Сумма перевода:',
      card: 'Карта:',
      holder: 'Владелец:',
      bank: 'Банк:',
      system: 'Система:',
      time_left: 'Осталось времени:',
      p2p_auto_confirm_hint: 'После перевода система подтвердит оплату автоматически, когда придёт уведомление банка.',
      topup_reserved_hint: 'Одна карта закреплена только за тобой на время таймера. После уведомления HUMO баланс зачислится автоматически.',
      copy_card: 'Скопировать карту',
      copy_amount: 'Скопировать сумму',
      cancel: 'Отменить',
      active_topup: 'Активное пополнение',
      no_active_topup: 'Нет активного пополнения. Введи сумму и получи свободную карту.',
      topup_load_failed: 'Не удалось загрузить статус пополнения.',
      enter_topup_amount: 'Введи сумму пополнения',
      card_reserved: 'Карта закреплена для пополнения',
      topup_cancelled: 'Пополнение отменено',
      invalid_promo: 'Промокод недействителен',
      enter_user_id: 'Введи User ID',
      not_enough_balance: 'Недостаточно баланса. Пополни баланс в профиле.',
      failed_place_order: 'Не удалось создать заказ',
      order_paid: '✅ Заказ оплачен!',
      order: 'Заказ',
      paid_from_balance: 'Списано с баланса:',
      auto_delivery: '📦 Автовыдача',
      auto_delivery_hint: 'Заказ оплачен и поставлен в очередь на выдачу через MooGold.',
      track_status_hint: 'Статус можно отслеживать в разделе “Мои заказы”.',
      view_my_orders: 'Открыть мои заказы',
      no_orders: 'Заказы не найдены',
      product: 'Товар',
      complete_payment: '💳 Завершить оплату',
      no_card_assigned: 'Карта не назначена. Обнови заказ или напиши в поддержку.',
      order_id: 'ID заказа:',
      check_payment: '🔄 Проверить оплату',
      manual_check: '🧾 Я оплатил / отправить на проверку',
      checking_payment_status: 'Проверяю статус оплаты...',
      sent_manual_check: 'Отправлено на ручную проверку',
      failed_submit_payment: 'Не удалось отправить оплату',
      referral_copied: 'Реферальная ссылка скопирована!',
      failed_referral: 'Не удалось получить реферальную ссылку',
      language: 'Язык'
    },
    en: {
      app_title: 'KADI — Top-up shop', loading: 'LOADING', home: 'Home', catalog: 'Catalog', orders: 'Orders', profile: 'Profile', search_placeholder: 'Search games, products, gift cards...', hero_title: 'Level Up Your Game', hero_subtitle: 'Game top-ups, Telegram Stars and Premium in one shop', explore_now: 'Explore Now →', categories: 'Categories', see_all: 'See All →', popular_now: '🔥 Popular Now', new: 'NEW', referral_program: 'Referral Program', referral_desc: 'Invite friends and earn bonuses on their purchases!', all: 'All', back: 'Back', back_to_cart: 'Back to Cart', cart: 'Shopping Cart', empty_cart: 'Your cart is empty', start_shopping: 'Start Shopping', subtotal: 'Subtotal', discount: 'Discount', total: 'Total', checkout: 'Checkout', proceed_checkout: 'Proceed to Checkout', account_details: '🎮 Account Details', target_label: 'User ID / Game ID / Telegram', target_placeholder: 'Enter your ID or username', server_label: 'Server, if required', server_placeholder: 'Enter server', promo_code: '🎟️ Promo Code', promo_placeholder: 'Enter promo code', apply: 'Apply', wallet_balance: '💰 Wallet Balance', paid_from_balance_hint: 'Your order will be paid from your balance.', available: 'Available:', topup_before_buying: 'Top up balance in Profile before buying.', items: 'Items', total_to_pay: 'Total to Pay', place_order: 'Place Order', pay_from_balance: 'Pay from Balance', insufficient_balance: 'Insufficient Balance — Top Up First', my_orders: 'My Orders', pending: 'Pending', checking: 'Checking', paid: 'Paid', completed: 'Completed', balance: 'Balance', spent: 'Spent', topup_balance: '💳 Top up Balance', topup_amount_placeholder: 'Amount in UZS', get_card: 'Get Card', support: 'Support', admin_panel: 'Admin Panel', dashboard: 'Dashboard', products: 'Products', users: 'Users', p2p_topups: 'P2P / Top-ups', system_check: 'System Check', total_users: 'Total Users', total_orders: 'Total Orders', total_revenue: 'Total Revenue', add_category: '+ Add Category', add_product: '+ Add Product', refresh: 'Refresh', search_users: 'Search users...', add_card: '+ Add Card', cards: 'Cards', topups_review: 'Top-ups / Review', run_check: 'Run Check', parse_humo_text: 'Parse HUMO Text', process_test_payment: 'Process Test Payment', no_products: 'No products found', instant_delivery: 'Instant digital delivery', select_amount: 'Select Amount', in_stock: '✓ In Stock', out_of_stock: '✗ Out of Stock', add_to_cart: 'Add to Cart', qty: 'Qty', copied: 'Copied', copy_failed: 'Copy failed', no_active_payment_session: 'No active payment session', p2p_payment: '💳 P2P Payment', pay_exact_amount: 'Pay exact amount:', transfer_amount: 'Transfer amount:', card: 'Card:', holder: 'Holder:', bank: 'Bank:', system: 'System:', time_left: 'Time left:', p2p_auto_confirm_hint: 'After transfer the system will confirm payment automatically when bank notification arrives.', topup_reserved_hint: 'One card is reserved only for you during this timer. After HUMO notification arrives, balance is credited automatically.', copy_card: 'Copy Card', copy_amount: 'Copy Amount', cancel: 'Cancel', active_topup: 'Active Top-up', no_active_topup: 'No active top-up. Enter amount and get a free card.', topup_load_failed: 'Could not load top-up status.', enter_topup_amount: 'Enter top-up amount', card_reserved: 'Card reserved for top-up', topup_cancelled: 'Top-up cancelled', invalid_promo: 'Invalid promo code', enter_user_id: 'Please enter your User ID', not_enough_balance: 'Not enough balance. Top up in Profile first.', failed_place_order: 'Failed to place order', order_paid: '✅ Order Paid!', order: 'Order', paid_from_balance: 'Paid from balance:', auto_delivery: '📦 Auto Delivery', auto_delivery_hint: 'Your order is paid and queued for MooGold delivery.', track_status_hint: 'You can track status in My Orders.', view_my_orders: 'View My Orders', no_orders: 'No orders found', product: 'Product', complete_payment: '💳 Complete Payment', no_card_assigned: 'No active payment card is assigned. Try refreshing this order or contact support.', order_id: 'Order ID:', check_payment: '🔄 Check Payment', manual_check: '🧾 I Paid / Send for Manual Check', checking_payment_status: 'Checking payment status...', sent_manual_check: 'Sent for manual check', failed_submit_payment: 'Failed to submit payment', referral_copied: 'Referral link copied!', failed_referral: 'Failed to get referral link', language: 'Language'
    },
    uz: {
      app_title: 'KADI — Donat do‘koni', loading: 'YUKLANMOQDA', home: 'Bosh sahifa', catalog: 'Katalog', orders: 'Buyurtmalar', profile: 'Profil', search_placeholder: 'O‘yinlar, mahsulotlar, sovg‘a kartalarini qidirish...', hero_title: 'O‘yinni tez to‘ldiring', hero_subtitle: 'Donatlar, Telegram Stars va Premium bitta do‘konda', explore_now: 'Mahsulotlarni ko‘rish →', categories: 'Kategoriyalar', see_all: 'Hammasi →', popular_now: '🔥 Ommabop', new: 'YANGI', referral_program: 'Referal dasturi', referral_desc: 'Do‘stlaringizni taklif qiling va xaridlardan bonus oling!', all: 'Hammasi', back: 'Orqaga', back_to_cart: 'Savatga qaytish', cart: 'Savat', empty_cart: 'Savat bo‘sh', start_shopping: 'Xaridni boshlash', subtotal: 'Oraliq summa', discount: 'Chegirma', total: 'Jami', checkout: 'Rasmiylashtirish', proceed_checkout: 'To‘lovga o‘tish', account_details: '🎮 Akkaunt ma’lumotlari', target_label: 'User ID / Game ID / Telegram', target_placeholder: 'ID yoki username kiriting', server_label: 'Server, kerak bo‘lsa', server_placeholder: 'Serverni kiriting', promo_code: '🎟️ Promokod', promo_placeholder: 'Promokodni kiriting', apply: 'Qo‘llash', wallet_balance: '💰 Hamyon balansi', paid_from_balance_hint: 'Buyurtma balansingizdan to‘lanadi.', available: 'Mavjud:', topup_before_buying: 'Xariddan oldin profil orqali balansni to‘ldiring.', items: 'Mahsulotlar', total_to_pay: 'To‘lov summasi', place_order: 'Buyurtma berish', pay_from_balance: 'Balansdan to‘lash', insufficient_balance: 'Balans yetarli emas — avval to‘ldiring', my_orders: 'Mening buyurtmalarim', pending: 'Kutilmoqda', checking: 'Tekshiruvda', paid: 'To‘langan', completed: 'Bajarildi', balance: 'Balans', spent: 'Sarflangan', topup_balance: '💳 Balansni to‘ldirish', topup_amount_placeholder: 'UZS miqdori', get_card: 'Karta olish', support: 'Yordam', admin_panel: 'Admin panel', dashboard: 'Dashboard', products: 'Mahsulotlar', users: 'Foydalanuvchilar', p2p_topups: 'P2P / To‘ldirishlar', system_check: 'Tizim tekshiruvi', total_users: 'Jami foydalanuvchilar', total_orders: 'Jami buyurtmalar', total_revenue: 'Daromad', add_category: '+ Kategoriya qo‘shish', add_product: '+ Mahsulot qo‘shish', refresh: 'Yangilash', search_users: 'Foydalanuvchilarni qidirish...', add_card: '+ Karta qo‘shish', cards: 'Kartalar', topups_review: 'To‘ldirishlar / Tekshiruv', run_check: 'Tekshirish', parse_humo_text: 'HUMO matnini ajratish', process_test_payment: 'Test to‘lov', no_products: 'Mahsulotlar topilmadi', instant_delivery: 'Tez raqamli yetkazib berish', select_amount: 'Variantni tanlang', in_stock: '✓ Mavjud', out_of_stock: '✗ Mavjud emas', add_to_cart: 'Savatga qo‘shish', qty: 'Soni', copied: 'Nusxalandi', copy_failed: 'Nusxalab bo‘lmadi', no_active_payment_session: 'Faol to‘lov sessiyasi yo‘q', p2p_payment: '💳 P2P to‘lov', pay_exact_amount: 'Aniq summani o‘tkazing:', transfer_amount: 'O‘tkazma summasi:', card: 'Karta:', holder: 'Egasi:', bank: 'Bank:', system: 'Tizim:', time_left: 'Qolgan vaqt:', p2p_auto_confirm_hint: 'O‘tkazmadan keyin bank xabari kelganda tizim to‘lovni avtomatik tasdiqlaydi.', topup_reserved_hint: 'Timer davomida bitta karta faqat sizga biriktiriladi. HUMO xabari kelgach balans avtomatik to‘ldiriladi.', copy_card: 'Kartani nusxalash', copy_amount: 'Summani nusxalash', cancel: 'Bekor qilish', active_topup: 'Faol to‘ldirish', no_active_topup: 'Faol to‘ldirish yo‘q. Summani kiriting va bo‘sh karta oling.', topup_load_failed: 'To‘ldirish holatini yuklab bo‘lmadi.', enter_topup_amount: 'To‘ldirish summasini kiriting', card_reserved: 'Karta to‘ldirish uchun band qilindi', topup_cancelled: 'To‘ldirish bekor qilindi', invalid_promo: 'Promokod noto‘g‘ri', enter_user_id: 'User ID kiriting', not_enough_balance: 'Balans yetarli emas. Avval profil orqali to‘ldiring.', failed_place_order: 'Buyurtma yaratilmadi', order_paid: '✅ Buyurtma to‘landi!', order: 'Buyurtma', paid_from_balance: 'Balansdan yechildi:', auto_delivery: '📦 Avto yetkazish', auto_delivery_hint: 'Buyurtma to‘landi va MooGold orqali yetkazish navbatiga qo‘yildi.', track_status_hint: 'Holatni “Mening buyurtmalarim” bo‘limida kuzatishingiz mumkin.', view_my_orders: 'Buyurtmalarimni ochish', no_orders: 'Buyurtmalar topilmadi', product: 'Mahsulot', complete_payment: '💳 To‘lovni yakunlash', no_card_assigned: 'Faol to‘lov kartasi biriktirilmagan. Buyurtmani yangilang yoki yordamga yozing.', order_id: 'Buyurtma ID:', check_payment: '🔄 To‘lovni tekshirish', manual_check: '🧾 To‘ladim / qo‘lda tekshiruvga yuborish', checking_payment_status: 'To‘lov holati tekshirilmoqda...', sent_manual_check: 'Qo‘lda tekshiruvga yuborildi', failed_submit_payment: 'To‘lovni yuborib bo‘lmadi', referral_copied: 'Referal havola nusxalandi!', failed_referral: 'Referal havolani olib bo‘lmadi', language: 'Til'
    }
  };

  function normalize(lang) {
    const l = String(lang || '').toLowerCase();
    if (l.startsWith('ru')) return 'ru';
    if (l.startsWith('uz')) return 'uz';
    if (l.startsWith('en')) return 'en';
    return 'ru';
  }

  function detectTelegramLanguage() {
    try {
      const code = window.Telegram?.WebApp?.initDataUnsafe?.user?.language_code;
      return normalize(code);
    } catch (_) {
      return 'ru';
    }
  }

  function getLang() {
    try {
      const storedLang = localStorage.getItem('app_language');
      if (storedLang) return normalize(storedLang);

      const urlLang = new URLSearchParams(window.location.search).get('lang');
      if (urlLang && LANGS.includes(normalize(urlLang))) {
        const normalizedUrlLang = normalize(urlLang);
        localStorage.setItem('app_language', normalizedUrlLang);
        return normalizedUrlLang;
      }

      return normalize(detectTelegramLanguage());
    } catch (_) {
      return 'ru';
    }
  }

  function t(key, params) {
    const lang = getLang();
    let value = (dict[lang] && dict[lang][key]) || (dict.ru && dict.ru[key]) || key;
    if (params && typeof value === 'string') {
      for (const [k, v] of Object.entries(params)) value = value.replaceAll(`{${k}}`, v);
    }
    return value;
  }

  function apply(root) {
    const base = root || document;
    document.documentElement.lang = getLang();
    base.querySelectorAll('[data-i18n]').forEach((el) => {
      el.textContent = t(el.dataset.i18n);
    });
    base.querySelectorAll('[data-i18n-placeholder]').forEach((el) => {
      el.setAttribute('placeholder', t(el.dataset.i18nPlaceholder));
    });
    base.querySelectorAll('[data-i18n-title]').forEach((el) => {
      el.setAttribute('title', t(el.dataset.i18nTitle));
    });
    const selector = document.getElementById('language-select');
    if (selector && selector.value !== getLang()) selector.value = getLang();
  }

  function setLang(lang) {
    const next = normalize(lang);
    try {
      localStorage.setItem('app_language', next);
    } catch (_) {}
    apply(document);
    window.dispatchEvent(new CustomEvent('languageChanged', { detail: { lang: next } }));
  }


  // KADI v10 UI additions / overrides
  const extra = {
    ru: {
      kadi_tagline: 'TOP UP. PLAY MORE.',
      fast_topups: 'Быстрые игровые пополнения',
      hero_title: 'Пополняй игры за пару кликов',
      hero_subtitle: "",
      topup: 'Пополнить',
      topup_balance_plain: 'Пополнить баланс',
      history: 'История',
      telegram_stars: 'Stars',
      help: 'Помощь',
      all_statuses: 'Все статусы',
      paid_needs_action: 'Оплачено — нужно действие',
      processing: 'В обработке',
      cancelled: 'Отменён',
      add_p2p_card: '+ Добавить карту',
      products_not_found: 'Товары не найдены',
      from: 'от',
      choose_package: 'Выберите пакет',
      required: 'обязательно',
      one_product_order: 'Сначала оформите текущий товар. В одном заказе — одна игра/услуга.',
      added_to_cart: 'Добавлено в корзину!',
      open_catalog: 'Открыть каталог',
      back_to_cart: 'Назад в корзину',
      payment: 'Оплата',
      recipient_details: '🎮 Данные получателя',
      player_id_label: 'ID игрока / Telegram username',
      enter_id: 'Введите ID',
      server_if_needed: 'Сервер, если нужен',
      enter_server_id: 'Введите Server ID',
      wallet_balance_simple: 'Баланс',
      order_paid_from_balance_hint: 'Заказ будет оплачен с баланса.',
      topup_profile_hint: 'Пополните баланс в профиле перед покупкой.',
      buy_from_balance: 'Купить с баланса',
      not_enough_topup: 'Недостаточно баланса — пополните',
      all_filter: 'Все',
      waiting: 'Ожидание',
      check: 'Проверка',
      ready: 'Готово',
      my_history: 'Моя история',
      admin_back: 'Назад',
      dashboard: 'Панель',
      admin_orders: 'Заказы',
      admin_products: 'Товары',
      admin_users: 'Пользователи',
      cards: 'Карты',
      topups_review: 'Пополнения / Проверка',
      run_check: 'Проверить',
      parse_humo_text: 'Разобрать HUMO текст',
      process_test_payment: 'Тест платежа',
      write_support: 'Напишите в поддержку через Telegram',
      target_username_placeholder: 'Введите Telegram username, например @username',
      target_id_placeholder: 'Введите ID',
      default_description: 'Моментальная цифровая выдача',
      target_region: 'Регион',
      open: 'Открыть',
      player: 'Игрок',
      items_count: '{count} товаров',
      cart_items_summary: '{positions} поз. • {quantity} тов.'
    },
    en: {
      kadi_tagline: 'TOP UP. PLAY MORE.',
      fast_topups: 'Fast game top-ups',
      hero_title: 'Top up games in a few clicks',
      hero_subtitle: "",
      topup: 'Top Up',
      topup_balance_plain: 'Top up balance',
      history: 'History',
      telegram_stars: 'Stars',
      help: 'Help',
      all_statuses: 'All statuses',
      paid_needs_action: 'Paid — needs action',
      processing: 'Processing',
      cancelled: 'Cancelled',
      add_p2p_card: '+ Add card',
      products_not_found: 'No products found',
      from: 'from',
      choose_package: 'Choose package',
      required: 'is required',
      one_product_order: 'Finish the current product first. One order can contain one game/service only.',
      added_to_cart: 'Added to cart!',
      open_catalog: 'Open catalog',
      back_to_cart: 'Back to cart',
      payment: 'Payment',
      recipient_details: '🎮 Recipient details',
      player_id_label: 'Player ID / Telegram username',
      enter_id: 'Enter ID',
      server_if_needed: 'Server, if required',
      enter_server_id: 'Enter Server ID',
      wallet_balance_simple: 'Balance',
      order_paid_from_balance_hint: 'The order will be paid from your balance.',
      topup_profile_hint: 'Top up your balance in Profile before buying.',
      buy_from_balance: 'Buy from balance',
      not_enough_topup: 'Insufficient balance — top up',
      all_filter: 'All',
      waiting: 'Waiting',
      check: 'Checking',
      ready: 'Ready',
      my_history: 'My history',
      admin_back: 'Back',
      dashboard: 'Dashboard',
      admin_orders: 'Orders',
      admin_products: 'Products',
      admin_users: 'Users',
      cards: 'Cards',
      topups_review: 'Top-ups / Review',
      run_check: 'Run check',
      parse_humo_text: 'Parse HUMO text',
      process_test_payment: 'Process test payment',
      write_support: 'Contact support via Telegram',
      target_username_placeholder: 'Enter Telegram username, e.g. @username',
      target_id_placeholder: 'Enter ID',
      default_description: 'Instant digital delivery',
      target_region: 'Region',
      open: 'Open',
      player: 'Player',
      items_count: '{count} items',
      cart_items_summary: '{positions} items • {quantity} pcs'
    },
    uz: {
      kadi_tagline: 'TOP UP. PLAY MORE.',
      fast_topups: 'Tez o‘yin to‘ldirishlar',
      hero_title: 'O‘yinlarni bir necha bosishda to‘ldiring',
      hero_subtitle: "",
      topup: 'To‘ldirish',
      topup_balance_plain: 'Balansni to‘ldirish',
      history: 'Tarix',
      telegram_stars: 'Stars',
      help: 'Yordam',
      all_statuses: 'Barcha statuslar',
      paid_needs_action: 'To‘langan — harakat kerak',
      processing: 'Jarayonda',
      cancelled: 'Bekor qilingan',
      add_p2p_card: '+ Karta qo‘shish',
      products_not_found: 'Mahsulotlar topilmadi',
      from: 'dan',
      choose_package: 'Paketni tanlang',
      required: 'majburiy',
      one_product_order: 'Avval joriy mahsulotni rasmiylashtiring. Bitta buyurtmada bitta o‘yin/xizmat bo‘ladi.',
      added_to_cart: 'Savatga qo‘shildi!',
      open_catalog: 'Katalogni ochish',
      back_to_cart: 'Savatga qaytish',
      payment: 'To‘lov',
      recipient_details: '🎮 Qabul qiluvchi ma’lumotlari',
      player_id_label: 'O‘yinchi ID / Telegram username',
      enter_id: 'ID kiriting',
      server_if_needed: 'Server, kerak bo‘lsa',
      enter_server_id: 'Server ID kiriting',
      wallet_balance_simple: 'Balans',
      order_paid_from_balance_hint: 'Buyurtma balansingizdan to‘lanadi.',
      topup_profile_hint: 'Xariddan oldin profilda balansni to‘ldiring.',
      buy_from_balance: 'Balansdan xarid qilish',
      not_enough_topup: 'Balans yetarli emas — to‘ldiring',
      all_filter: 'Hammasi',
      waiting: 'Kutilmoqda',
      check: 'Tekshiruv',
      ready: 'Tayyor',
      my_history: 'Mening tarixim',
      admin_back: 'Orqaga',
      dashboard: 'Panel',
      admin_orders: 'Buyurtmalar',
      admin_products: 'Mahsulotlar',
      admin_users: 'Foydalanuvchilar',
      cards: 'Kartalar',
      topups_review: 'To‘ldirishlar / Tekshiruv',
      run_check: 'Tekshirish',
      parse_humo_text: 'HUMO matnini ajratish',
      process_test_payment: 'Test to‘lovni bajarish',
      write_support: 'Telegram orqali yordamga yozing',
      target_username_placeholder: 'Telegram usernameni kiriting, masalan @username',
      target_id_placeholder: 'ID kiriting',
      default_description: 'Tez raqamli yetkazib berish',
      target_region: 'Hudud',
      open: 'Ochish',
      player: 'O‘yinchi',
      items_count: '{count} ta mahsulot',
      cart_items_summary: '{positions} poz. • {quantity} dona'
    }
  };
  for (const lang of LANGS) Object.assign(dict[lang], extra[lang] || {});

  window.I18N = { dict, langs: LANGS, getLang, setLang, t, apply };
  window.t = t;
})();
