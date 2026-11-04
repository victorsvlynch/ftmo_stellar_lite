//+------------------------------------------------------------------+

//|                                   StellarLite_Webhook_Bridge.mq5 |

//|             FundedNext Stellar Lite ($10,000) - Webhook Bridge EA |

//|          Conecta MetaTrader 5 con el Motor Cuantitativo 24/7 OCI |

//+------------------------------------------------------------------+

#property copyright   "FundedNext Stellar Lite Quantitative Engine"

#property link        "https://github.com/victorsvlynch/ftmo_stellar_lite"

#property version     "2.20"

#property description "Expert Advisor de Enlace Webhook con el Bot de Python en Oracle Cloud VPS (157.137.225.144:8000)."

#property description "Recibe senales institucionales de NY_OPEN (Oro / XAUUSD) y ejecuta ordenes con SL, TP y Break-Even."



#include <Trade\Trade.mqh>



//--- Parametros de Entrada

input group "--- Servidor Oracle Cloud VPS ---"

input string InpServerUrl       = "http://127.0.0.1:8000";       // URL Webhook (127.0.0.1:8000 o 157.137.225.144:8000)

input int    InpPollIntervalSec = 1;                              // Frecuencia de Sondeo (segundos)



input group "--- Configuracion de Trading Institucional ---"

input ulong  InpMagicNumber     = 505001;                         // Magic Number Institucional

input ulong  InpDeviationPoints = 30;                             // Slippage Maximo Permitido (puntos)

input string InpPreferredSymbol = "XAUUSD";                       // Simbolo Preferido (o vacio para usar el grafico)

input bool   InpEnableSP500     = true;                           // Activar S&P 500 (US500) [ACTIVO OFICIAL]                          // Activar S&P 500 (US500) [Guardado en Standby]



//--- Instancias Globales

CTrade         ExtTrade;

datetime       ExtLastPollTime = 0;

string         ExtServerStatus = "DESCONECTADO";

string         ExtLastActionMsg = "Esperando primera conexion...";

int            ExtConsecutiveErrors = 0;

int            ExtCloudZeroTradeConsecutiveCycles = 0;



//+------------------------------------------------------------------+

//| Helper: Comprobar existencia de una clave en un JSON plano       |

//+------------------------------------------------------------------+

bool JsonHasKey(const string json, const string key)

{

   string searchKey = "\"" + key + "\":";

   return (StringFind(json, searchKey) >= 0);

}



//+------------------------------------------------------------------+

//| Helper: Extraer valor de string de un JSON plano                 |

//+------------------------------------------------------------------+

string JsonExtractString(const string json, const string key)

{

   string searchKey = "\"" + key + "\":";

   int pos = StringFind(json, searchKey);

   if(pos < 0) return "";

   

   int start = pos + StringLen(searchKey);

   while(start < StringLen(json) && (StringGetCharacter(json, start) == ' ' || StringGetCharacter(json, start) == '\"'))

      start++;

      

   int end = start;

   while(end < StringLen(json) && StringGetCharacter(json, end) != '\"' && StringGetCharacter(json, end) != ',' && StringGetCharacter(json, end) != '}')

      end++;

      

   return StringSubstr(json, start, end - start);

}



//+------------------------------------------------------------------+

//| Helper: Extraer valor numerico o booleano de un JSON plano       |

//+------------------------------------------------------------------+

double JsonExtractDouble(const string json, const string key)

{

   if(!JsonHasKey(json, key)) return -1.0;

   string val = JsonExtractString(json, key);

   return StringToDouble(val);

}



bool JsonExtractBool(const string json, const string key)

{

   string searchKey = "\"" + key + "\":";

   int pos = StringFind(json, searchKey);

   if(pos < 0) return false;

   int start = pos + StringLen(searchKey);

   string sub = StringSubstr(json, start, 10);

   StringToLower(sub);

   return (StringFind(sub, "true") >= 0);

}



//+------------------------------------------------------------------+

//| Resolver simbolo real del broker (Oro, EUR/USD, S&P 500, etc.)   |

//+------------------------------------------------------------------+

string ResolveBrokerSymbol(const string requestedSymbol)

{

   string clean = requestedSymbol;

   StringToUpper(clean);

   StringReplace(clean, "=X", "");

   StringReplace(clean, "=F", "");

   StringReplace(clean, "/", "");



   // Bloqueo explícito de Nasdaq 100 (Inactivo por política de riesgo institucional)

   if(StringFind(clean, "100") >= 0 || StringFind(clean, "NAS") >= 0 || StringFind(clean, "USTEC") >= 0 || StringFind(clean, "NQ") >= 0)

   {

      PrintFormat("[EA MT5] [INACTIVO] El activo Nasdaq 100 (%s) esta desactivado por configuracion institucional.", requestedSymbol);

      return "INACTIVE";

   }



   if(SymbolInfoDouble(requestedSymbol, SYMBOL_BID) > 0)

      return requestedSymbol;



   // A. S&P 500 (Guardado en Standby - se activa cambiando InpEnableSP500 = true)

   if(StringFind(clean, "500") >= 0 || StringFind(clean, "SPX") >= 0 || StringFind(clean, "ES") >= 0)

   {

      if(!InpEnableSP500)

         return "INACTIVE";

      string candidates[] = {"US500", "US500.cash", "SPX500", "USA500", "US500m", "US500.raw", "US500.pro", "SP500", "ES"};

      for(int i = 0; i < ArraySize(candidates); i++)

         if(SymbolInfoDouble(candidates[i], SYMBOL_BID) > 0) return candidates[i];

   }

   // B. EUR/USD

   else if(StringFind(clean, "EUR") >= 0)

   {

      string candidates[] = {"EURUSD", "EURUSDm", "EURUSD.raw", "EURUSD.pro", "EURUSDb", "EURUSD.cash", "EURUSD+"};

      for(int i = 0; i < ArraySize(candidates); i++)

         if(SymbolInfoDouble(candidates[i], SYMBOL_BID) > 0) return candidates[i];

   }

   // C. USD/JPY y AUD/USD (Inactivos: Portafolio Exclusivo Oro, EURUSD y SP500)

   else if(StringFind(clean, "JPY") >= 0 || StringFind(clean, "AUD") >= 0 || StringFind(clean, "GBP") >= 0 || StringFind(clean, "BTC") >= 0)

   {

      PrintFormat("[EA MT5] [INACTIVO] El activo %s esta desactivado (solo Oro, EUR/USD y SP500 activos).", requestedSymbol);

      return "INACTIVE";

   }

   // D. Oro / XAUUSD

   else

   {

      string candidates[] = {"XAUUSD", "GOLD", "XAUUSDm", "XAUUSD.raw", "XAUUSD.pro", "XAUUSDb"};

      for(int i = 0; i < ArraySize(candidates); i++)

         if(SymbolInfoDouble(candidates[i], SYMBOL_BID) > 0) return candidates[i];

   }



   // Busqueda inteligente en la lista completa de simbolos del broker

   int total = SymbolsTotal(false);

   for(int i = 0; i < total; i++)

   {

      string sName = SymbolName(i, false);

      string sUpper = sName;

      StringToUpper(sUpper);

      if(InpEnableSP500 && StringFind(clean, "500") >= 0 && (StringFind(sUpper, "500") >= 0 || StringFind(sUpper, "SPX") >= 0))

         return sName;

      if(StringFind(clean, "EUR") >= 0 && StringFind(sUpper, "EUR") >= 0 && StringFind(sUpper, "USD") >= 0)

         return sName;

      if(StringFind(clean, "JPY") >= 0 && StringFind(sUpper, "USD") >= 0 && StringFind(sUpper, "JPY") >= 0)

         return sName;

      if(StringFind(clean, "AUD") >= 0 && StringFind(sUpper, "AUD") >= 0 && StringFind(sUpper, "USD") >= 0)

         return sName;

      if((StringFind(clean, "XAU") >= 0 || StringFind(clean, "GC") >= 0) && (StringFind(sUpper, "XAU") >= 0 || StringFind(sUpper, "GOLD") >= 0))

         return sName;

   }



   return _Symbol;

}



//+------------------------------------------------------------------+

//| Realizar peticion HTTP WebRequest                                |

//+------------------------------------------------------------------+

bool SendHttpRequest(const string method, const string url, const string postData, string &responseOut, int &statusCodeOut)

{

   char postDataArr[];

   char resultArr[];

   string headers = "Content-Type: application/json\r\n";

   string resultHeaders;

   

   if(StringLen(postData) > 0)

      StringToCharArray(postData, postDataArr, 0, StringLen(postData));

   else

      ArrayResize(postDataArr, 0);

      

   ResetLastError();

   int res = WebRequest(

      method,

      url,

      headers,

      3000,

      postDataArr,

      resultArr,

      resultHeaders

   );

   

   statusCodeOut = res;

   if(res == 200)

   {

      responseOut = CharArrayToString(resultArr);

      return true;

   }

   

   int err = GetLastError();

   if(err == 4014) // ERR_WEBREQUEST_NOT_ALLOWED

   {

      PrintFormat("[ERROR FATAL] WebRequest no permitido para la URL '%s'. Agregala en Herramientas -> Opciones -> Asesores Expertos.", InpServerUrl);

      ExtServerStatus = "ERROR: URL NO AUTORIZADA EN MT5 (Herramientas -> Opciones -> Asesores Expertos)";

   }

   else

   {

      PrintFormat("[WEB] WebRequest fallo (Cod: %d, Error: %d)", res, err);

   }

   return false;

}



//+------------------------------------------------------------------+

//| Confirmar accion completada hacia Oracle Cloud                   |

//+------------------------------------------------------------------+

void ConfirmActionToCloud(int actionId, ulong ticket, double price, bool success)

{

   string confirmUrl = InpServerUrl + "/api/confirm";

   string payload = StringFormat(

      "{\"action_id\":%d,\"ticket\":%I64u,\"price\":%.5f,\"success\":%s}",

      actionId, ticket, price, success ? "true" : "false"

   );

   string resp;

   int status;

   SendHttpRequest("POST", confirmUrl, payload, resp, status);

}



//+------------------------------------------------------------------+

//| Actualizar tablero visual en el grafico                          |

//+------------------------------------------------------------------+

void UpdateChartDashboard()

{

   string sep = "========================================================================\n";

   string text = "";

   text += sep;

   text += "  FUNDEDNEXT STELLAR LITE ($10,000) -- WEBHOOK BRIDGE EA MT5\n";

   text += "  Estrategia Ganadora: NY_OPEN (Oro / XAUUSD) | R:R 1:2 + Break-Even\n";

   text += sep;

   text += StringFormat("  Servidor Oracle VPS: %s\n", InpServerUrl);

   text += StringFormat("  Estado Conexion    : %s\n", ExtServerStatus);

   text += StringFormat("  Ultimo Sondeo      : %s (Cada %d seg)\n", TimeToString(TimeCurrent(), TIME_MINUTES|TIME_SECONDS), InpPollIntervalSec);

   text += StringFormat("  Magic Number       : %I64u | Slippage: %I64u pts\n", InpMagicNumber, InpDeviationPoints);

   text += StringFormat("  Simbolo Operado    : %s\n", ResolveBrokerSymbol(InpPreferredSymbol));

   text += sep;

   text += StringFormat("  Ultima Accion      : %s\n", ExtLastActionMsg);

   text += sep;

   text += "  >> Monitoreo 24/7 Activo | Sincronizado con Python en Oracle Cloud <<\n";

   Comment(text);

}



//+------------------------------------------------------------------+

//| Procesar accion recibida desde Oracle Cloud                      |

//+------------------------------------------------------------------+

//+------------------------------------------------------------------+

//| Perfil de Escalera Break-Even+ y Trailing por Clase de Activo    |

//+------------------------------------------------------------------+

void GetAssetTrailingProfile(

   string sym,

   int digits,

   double pt,

   double initialRiskDist,

   double &beTriggerR,

   double &beOffset,

   double &lock1TriggerR,

   double &lock1GainR,

   double &lock2TriggerR,

   double &lock2GainR,

   double &trailTriggerR,

   int &trailBarsM15,

   double &trailBufferR,

   double &stagnationRangeR,

   double &minTightBuffer

)

{

   string s = sym;

   StringToUpper(s);

   bool isGold  = (StringFind(s, "XAU") >= 0 || StringFind(s, "GOLD") >= 0 || StringFind(s, "GC") >= 0);

   bool isJpy   = (!isGold && StringFind(s, "JPY") >= 0);

   bool isAud   = (!isGold && !isJpy && StringFind(s, "AUD") >= 0);

   bool isForex = (!isGold && !isJpy && !isAud && digits >= 4);



   if(isGold)

   {

      // XAUUSD (Oro): BE+ ($0.80) a +1.00R | Candado 1 (+0.60R) a +1.40R | Candado 2 (+1.10R) a +1.75R | Trailing M15 (3 velas / 1 vela en estancamiento <=0.35R)

      beTriggerR       = 1.00;

      beOffset         = MathMin(0.80, initialRiskDist * 0.15);

      lock1TriggerR    = 1.40;

      lock1GainR       = 0.60;

      lock2TriggerR    = 1.75;

      lock2GainR       = 1.10;

      trailTriggerR    = 1.75;

      trailBarsM15     = 3;

      trailBufferR     = 0.10;

      stagnationRangeR = 0.35;

      minTightBuffer   = 0.80;

   }

   else if(isJpy)

   {

      // USDJPY (Forex Bonos US/NY - Alta Eficiencia Tendencial 44.9%, ADR ~87p):

      // BE+ (1.5 pips = 0.015) a +0.95R | Candado 1 (+0.55R) a +1.35R | Candado 2 (+1.15R) a +1.70R |

      // Trailing M15 Persistente (2 velas + 0.08R / 1 vela + 1.5 pips en estancamiento <=0.30R o Pre-Rollover)

      double pip       = (digits == 5 || digits == 3) ? (10.0 * pt) : pt;

      beTriggerR       = 0.95;

      beOffset         = MathMin(1.5 * pip, initialRiskDist * 0.15);

      lock1TriggerR    = 1.35;

      lock1GainR       = 0.55;

      lock2TriggerR    = 1.70;

      lock2GainR       = 1.15;

      trailTriggerR    = 1.70;

      trailBarsM15     = 2;

      trailBufferR     = 0.08;

      stagnationRangeR = 0.30;

      minTightBuffer   = 1.5 * pip;

   }

   else if(isAud)

   {

      // AUDUSD (Forex Pacifico/NY - Menor ADR): BE+ (1.2 pips) a +0.95R | Candado 1 (+0.55R) a +1.30R | Candado 2 (+1.10R) a +1.65R | Trailing M15 (2 velas / 1 vela en estancamiento <=0.28R)

      double pip       = (digits == 5 || digits == 3) ? (10.0 * pt) : pt;

      beTriggerR       = 0.95;

      beOffset         = MathMin(1.2 * pip, initialRiskDist * 0.15);

      lock1TriggerR    = 1.30;

      lock1GainR       = 0.55;

      lock2TriggerR    = 1.65;

      lock2GainR       = 1.10;

      trailTriggerR    = 1.65;

      trailBarsM15     = 2;

      trailBufferR     = 0.08;

      stagnationRangeR = 0.28;

      minTightBuffer   = 1.2 * pip;

   }

   else if(isForex)

   {

      // EURUSD (Forex Europeo/NY): BE+ (1.5 pips) a +0.95R | Candado 1 (+0.50R) a +1.35R | Candado 2 (+1.10R) a +1.70R | Trailing M15 (3 velas / 1 vela en estancamiento <=0.30R)

      double pip       = (digits == 5 || digits == 3) ? (10.0 * pt) : pt;

      beTriggerR       = 0.95;

      beOffset         = MathMin(1.5 * pip, initialRiskDist * 0.15);

      lock1TriggerR    = 1.35;

      lock1GainR       = 0.50;

      lock2TriggerR    = 1.70;

      lock2GainR       = 1.10;

      trailTriggerR    = 1.70;

      trailBarsM15     = 3;

      trailBufferR     = 0.10;

      stagnationRangeR = 0.30;

      minTightBuffer   = 1.2 * pip;

   }

   else

   {

      // S&P 500 (US500 / ES - Standby): BE+ (1.0 pt) a +1.00R | Candado 1 (+0.60R) a +1.35R | Candado 2 (+1.15R) a +1.70R | Trailing M15 (2 velas / 1 vela en estancamiento <=0.30R)

      beTriggerR       = 1.00;

      beOffset         = MathMin(1.00, initialRiskDist * 0.15);

      lock1TriggerR    = 1.35;

      lock1GainR       = 0.60;

      lock2TriggerR    = 1.70;

      lock2GainR       = 1.15;

      trailTriggerR    = 1.70;

      trailBarsM15     = 2;

      trailBufferR     = 0.10;

      stagnationRangeR = 0.30;

      minTightBuffer   = 1.00;

   }

}



void ProcessCloudAction(const string json)

{

   int actionId = (int)JsonExtractDouble(json, "action_id");

   string action = JsonExtractString(json, "action");

   string symReq = JsonExtractString(json, "symbol");

   double lots = JsonExtractDouble(json, "lots");

   double price = JsonExtractDouble(json, "price");

   double sl = JsonExtractDouble(json, "sl");

   double tp = JsonExtractDouble(json, "tp");

   int tradeId = (int)JsonExtractDouble(json, "trade_id");

   string comment = JsonExtractString(json, "comment");

   if(StringLen(comment) == 0) comment = "FundedNext NY_ORB";

   

   string realSymbol = ResolveBrokerSymbol(symReq);

   if(realSymbol == "INACTIVE" || realSymbol == "")

   {

      PrintFormat("[EA MT5] [INACTIVO] Accion #%d descartada: El activo '%s' esta desactivado por politica institucional.", actionId, symReq);

      ExtLastActionMsg = StringFormat("Activo %s desactivado institucionalmente.", symReq);

      ConfirmActionToCloud(actionId, 0, 0.0, true);

      return;

   }

   

   // A. APERTURA DE COMPRA (BUY)

   if(action == "OPEN_BUY")

   {

      // Verificar si ya tenemos posicion abierta en este simbolo con ese magic

      bool alreadyOpen = false;

      for(int i = PositionsTotal() - 1; i >= 0; i--)

      {

         ulong ticket = PositionGetTicket(i);

         if(ticket > 0 && PositionGetInteger(POSITION_MAGIC) == InpMagicNumber && PositionGetString(POSITION_SYMBOL) == realSymbol)

         {

            alreadyOpen = true;

            break;

         }

      }

      

      if(!alreadyOpen)

      {

         MqlTick tick;

         if(!SymbolInfoTick(realSymbol, tick))

         {

            ExtLastActionMsg = "Error: SymbolInfoTick fallo para " + realSymbol;

            ConfirmActionToCloud(actionId, 0, 0.0, false);

            return;

         }



         double askPrice = tick.ask;

         int digits = (int)SymbolInfoInteger(realSymbol, SYMBOL_DIGITS);



         // Calcular distancias institucionales (R:R 1:2) relativas al precio de ejecucion

         double slDist = (sl > 0 && price > 0) ? MathAbs(price - sl) : 0.0;

         double tpDist = (tp > 0 && price > 0) ? MathAbs(price - tp) : 0.0;

         if(slDist <= 0.0)

         {

            if(digits >= 4) slDist = 250 * SymbolInfoDouble(realSymbol, SYMBOL_POINT); // ~25 pips en Forex

            else if(askPrice > 1000) slDist = (StringFind(realSymbol, "XAU") >= 0 || StringFind(realSymbol, "GOLD") >= 0) ? 6.50 : 15.0; // Oro o Indices

            else slDist = 50 * SymbolInfoDouble(realSymbol, SYMBOL_POINT);

         }

         if(tpDist <= 0.0) tpDist = slDist * 2.0;



         // Detectar si la cotizacion del broker difiere de la fuente externa por escala de contrato

         bool priceScaleMismatch = (price > 0 && (MathAbs(askPrice - price) / askPrice) > 0.02);



         double slPrice, tpPrice;

         if(priceScaleMismatch || sl <= 0 || sl >= askPrice)

            slPrice = NormalizeDouble(askPrice - slDist, digits);

         else

            slPrice = NormalizeDouble(sl, digits);



         if(priceScaleMismatch || tp <= 0 || tp <= askPrice)

            tpPrice = NormalizeDouble(askPrice + tpDist, digits);

         else

            tpPrice = NormalizeDouble(tp, digits);



         PrintFormat("[EA MT5] Ejecutando COMPRA institucional: %s %.2f lotes @ %.2f | SL: %.2f | TP: %.2f (Dist SL: %.2f, TP: %.2f)", 

                     realSymbol, lots, askPrice, slPrice, tpPrice, slDist, tpDist);



         bool orderSuccess = false;

         ENUM_ORDER_TYPE_FILLING fillModes[] = {ORDER_FILLING_IOC, ORDER_FILLING_FOK, ORDER_FILLING_RETURN};

         for(int f = 0; f < ArraySize(fillModes); f++)

         {

            ExtTrade.SetTypeFilling(fillModes[f]);

            if(ExtTrade.Buy(lots, realSymbol, askPrice, slPrice, tpPrice, comment))

            {

               orderSuccess = true;

               break;

            }

         }



         // Fallback para brokers con Market Execution (donde SL/TP no pueden enviarse en la orden directa)

         if(!orderSuccess)

         {

            for(int f = 0; f < ArraySize(fillModes); f++)

            {

               ExtTrade.SetTypeFilling(fillModes[f]);

               if(ExtTrade.Buy(lots, realSymbol, askPrice, 0.0, 0.0, comment))

               {

                  orderSuccess = true;

                  ulong ordTicket = ExtTrade.ResultOrder();

                  Sleep(150);

                  ExtTrade.PositionModify(ordTicket, slPrice, tpPrice);

                  PrintFormat("[EA MT5] [MARKET EXECUTION] SL y TP aplicados via PositionModify -> Ticket #%I64u", ordTicket);

                  break;

               }

            }

         }



         if(orderSuccess)

         {

            ulong orderTicket = ExtTrade.ResultOrder();

            double fillPrice = ExtTrade.ResultPrice();

            ExtLastActionMsg = StringFormat("BUY #%I64u (%.2f Lotes) ejecutada @ %.2f", orderTicket, lots, fillPrice);

            PrintFormat("[EA MT5] [EXITO] Orden BUY colocada -> Ticket: #%I64u", orderTicket);

            ConfirmActionToCloud(actionId, orderTicket, fillPrice, true);

         }

         else

         {

            int err = GetLastError();

            ExtLastActionMsg = StringFormat("Error al abrir BUY: %d - %s", err, ExtTrade.ResultComment());

            PrintFormat("[EA MT5] [FALLO] No se pudo abrir BUY: %d - %s", err, ExtTrade.ResultComment());

            ConfirmActionToCloud(actionId, 0, 0.0, false);

         }

      }

      else

      {

         PrintFormat("[EA MT5] Posicion con Magic %I64u ya existe. Omitiendo duplicado.", InpMagicNumber);

         ConfirmActionToCloud(actionId, 0, 0.0, true);

      }

   }

   

   // B. APERTURA DE VENTA (SELL)

   else if(action == "OPEN_SELL")

   {

      bool alreadyOpen = false;

      for(int i = PositionsTotal() - 1; i >= 0; i--)

      {

         ulong ticket = PositionGetTicket(i);

         if(ticket > 0 && PositionGetInteger(POSITION_MAGIC) == InpMagicNumber && PositionGetString(POSITION_SYMBOL) == realSymbol)

         {

            alreadyOpen = true;

            break;

         }

      }

      

      if(!alreadyOpen)

      {

         MqlTick tick;

         if(!SymbolInfoTick(realSymbol, tick))

         {

            ExtLastActionMsg = "Error: SymbolInfoTick fallo para " + realSymbol;

            ConfirmActionToCloud(actionId, 0, 0.0, false);

            return;

         }



         double bidPrice = tick.bid;

         int digits = (int)SymbolInfoInteger(realSymbol, SYMBOL_DIGITS);



         // Calcular distancias institucionales (R:R 1:2) relativas al precio de ejecucion

         double slDist = (sl > 0 && price > 0) ? MathAbs(sl - price) : 0.0;

         double tpDist = (tp > 0 && price > 0) ? MathAbs(price - tp) : 0.0;

         if(slDist <= 0.0)

         {

            if(digits >= 4) slDist = 250 * SymbolInfoDouble(realSymbol, SYMBOL_POINT); // ~25 pips en Forex

            else if(bidPrice > 1000) slDist = (StringFind(realSymbol, "XAU") >= 0 || StringFind(realSymbol, "GOLD") >= 0) ? 6.50 : 15.0; // Oro o Indices

            else slDist = 50 * SymbolInfoDouble(realSymbol, SYMBOL_POINT);

         }

         if(tpDist <= 0.0) tpDist = slDist * 2.0;



         // Detectar si la cotizacion del broker difiere de la fuente externa por escala de contrato

         bool priceScaleMismatch = (price > 0 && (MathAbs(bidPrice - price) / bidPrice) > 0.02);



         double slPrice, tpPrice;

         if(priceScaleMismatch || sl <= 0 || sl <= bidPrice)

            slPrice = NormalizeDouble(bidPrice + slDist, digits);

         else

            slPrice = NormalizeDouble(sl, digits);



         if(priceScaleMismatch || tp <= 0 || tp >= bidPrice)

            tpPrice = NormalizeDouble(bidPrice - tpDist, digits);

         else

            tpPrice = NormalizeDouble(tp, digits);



         PrintFormat("[EA MT5] Ejecutando VENTA institucional: %s %.2f lotes @ %.2f | SL: %.2f | TP: %.2f (Dist SL: %.2f, TP: %.2f)", 

                     realSymbol, lots, bidPrice, slPrice, tpPrice, slDist, tpDist);



         bool orderSuccess = false;

         ENUM_ORDER_TYPE_FILLING fillModes[] = {ORDER_FILLING_IOC, ORDER_FILLING_FOK, ORDER_FILLING_RETURN};

         for(int f = 0; f < ArraySize(fillModes); f++)

         {

            ExtTrade.SetTypeFilling(fillModes[f]);

            if(ExtTrade.Sell(lots, realSymbol, bidPrice, slPrice, tpPrice, comment))

            {

               orderSuccess = true;

               break;

            }

         }



         // Fallback para brokers con Market Execution (donde SL/TP no pueden enviarse en la orden directa)

         if(!orderSuccess)

         {

            for(int f = 0; f < ArraySize(fillModes); f++)

            {

               ExtTrade.SetTypeFilling(fillModes[f]);

               if(ExtTrade.Sell(lots, realSymbol, bidPrice, 0.0, 0.0, comment))

               {

                  orderSuccess = true;

                  ulong ordTicket = ExtTrade.ResultOrder();

                  Sleep(150);

                  ExtTrade.PositionModify(ordTicket, slPrice, tpPrice);

                  PrintFormat("[EA MT5] [MARKET EXECUTION] SL y TP aplicados via PositionModify -> Ticket #%I64u", ordTicket);

                  break;

               }

            }

         }



         if(orderSuccess)

         {

            ulong orderTicket = ExtTrade.ResultOrder();

            double fillPrice = ExtTrade.ResultPrice();

            ExtLastActionMsg = StringFormat("SELL #%I64u (%.2f Lotes) ejecutada @ %.2f", orderTicket, lots, fillPrice);

            PrintFormat("[EA MT5] [EXITO] Orden SELL colocada -> Ticket: #%I64u", orderTicket);

            ConfirmActionToCloud(actionId, orderTicket, fillPrice, true);

         }

         else

         {

            int err = GetLastError();

            ExtLastActionMsg = StringFormat("Error al abrir SELL: %d - %s", err, ExtTrade.ResultComment());

            PrintFormat("[EA MT5] [FALLO] No se pudo abrir SELL: %d - %s", err, ExtTrade.ResultComment());

            ConfirmActionToCloud(actionId, 0, 0.0, false);

         }

      }

      else

      {

         ConfirmActionToCloud(actionId, 0, 0.0, true);

      }

   }

   

   // C. MODIFICACION DE STOP LOSS A BREAK-EVEN / ESCALERA DE CANDADOS

   else if(action == "MODIFY_SL")

   {

      bool found = false;

      for(int i = PositionsTotal() - 1; i >= 0; i--)

      {

         ulong ticket = PositionGetTicket(i);

         if(ticket > 0 && PositionGetInteger(POSITION_MAGIC) == InpMagicNumber && PositionGetString(POSITION_SYMBOL) == realSymbol)

         {

            found = true;

            string posSym = PositionGetString(POSITION_SYMBOL);

            ENUM_POSITION_TYPE pType = (ENUM_POSITION_TYPE)PositionGetInteger(POSITION_TYPE);

            double curTp = PositionGetDouble(POSITION_TP);

            double curSl = PositionGetDouble(POSITION_SL);

            double entryPrice = PositionGetDouble(POSITION_PRICE_OPEN);

            int digits = (int)SymbolInfoInteger(posSym, SYMBOL_DIGITS);

            double pt = SymbolInfoDouble(posSym, SYMBOL_POINT);



            double initialRiskDist = (curTp > 0.0 && MathAbs(curTp - entryPrice) > (10 * pt))

                                     ? (MathAbs(curTp - entryPrice) / 2.0)

                                     : MathAbs(entryPrice - curSl);

            double beTriggerR = 1.0, beOffset = 0.0, lock1TriggerR = 1.35, lock1GainR = 0.50, lock2TriggerR = 1.70, lock2GainR = 1.10, trailTriggerR = 1.70, trailBufferR = 0.10, stagnationRangeR = 0.30, minTightBuffer = 0.0;

            int trailBarsM15 = 3;

            GetAssetTrailingProfile(posSym, digits, pt, initialRiskDist, beTriggerR, beOffset, lock1TriggerR, lock1GainR, lock2TriggerR, lock2GainR, trailTriggerR, trailBarsM15, trailBufferR, stagnationRangeR, minTightBuffer);



            double newSl = NormalizeDouble(sl, digits);

            if(StringFind(comment, "ESCUDO_PRE_ROLLOVER") >= 0)

            {

               double prerollR = (StringFind(posSym, "XAU") >= 0 || StringFind(posSym, "GOLD") >= 0) ? 1.35 : 1.30;

               double off = initialRiskDist * prerollR;

               newSl = NormalizeDouble((pType == POSITION_TYPE_BUY) ? (entryPrice + off) : (entryPrice - off), digits);

            }

            else if(StringFind(comment, "CANDADO_NIVEL_3") >= 0)

            {

               double off = initialRiskDist * lock2GainR;

               newSl = NormalizeDouble((pType == POSITION_TYPE_BUY) ? (entryPrice + off) : (entryPrice - off), digits);

            }

            else if(StringFind(comment, "CANDADO_NIVEL_2") >= 0)

            {

               double off = initialRiskDist * lock1GainR;

               newSl = NormalizeDouble((pType == POSITION_TYPE_BUY) ? (entryPrice + off) : (entryPrice - off), digits);

            }

            else if(StringFind(comment, "Break-Even") >= 0 || StringFind(comment, "BREAK_EVEN") >= 0 || (sl > 0 && MathAbs(entryPrice - sl) > 20.0))

            {

               newSl = NormalizeDouble((pType == POSITION_TYPE_BUY) ? (entryPrice + beOffset) : (entryPrice - beOffset), digits);

            }



            // A. Regla Monotonica (Ratchet): nunca retroceder un SL que ya este igual o mejor posicionado

            bool alreadyBetterOrEqual = false;

            if(pType == POSITION_TYPE_BUY && curSl > 0.0 && curSl >= (newSl - (pt * 0.5)))

               alreadyBetterOrEqual = true;

            if(pType == POSITION_TYPE_SELL && curSl > 0.0 && curSl <= (newSl + (pt * 0.5)))

               alreadyBetterOrEqual = true;



            if(alreadyBetterOrEqual || MathAbs(curSl - newSl) < (pt * 0.5))

            {

               ExtLastActionMsg = StringFormat("Posicion #%I64u ya blindada (SL: %.*f)", ticket, digits, curSl);

               PrintFormat("[EA MT5] [AL DIA] Posicion #%I64u ya tiene SL igual o mejor (%.*f vs %.*f). Confirmando accion #%d a la nube.", 

                           ticket, digits, curSl, digits, newSl, actionId);

               ConfirmActionToCloud(actionId, ticket, curSl, true);

               break;

            }



            PrintFormat("[EA MT5] Blindando posicion #%I64u (%s): Nuevo SL: %.*f (Precio Entrada: %.*f)", 

                        ticket, comment, digits, newSl, digits, entryPrice);

            if(ExtTrade.PositionModify(ticket, newSl, curTp))

            {

               ExtLastActionMsg = StringFormat("Posicion #%I64u blindada (%s -> SL: %.*f)", ticket, comment, digits, newSl);

               PrintFormat("[EA MT5] [EXITO] Posicion #%I64u modificada a SL %.*f.", ticket, digits, newSl);

               ConfirmActionToCloud(actionId, ticket, newSl, true);

            }

            else

            {

               uint retCode = ExtTrade.ResultRetcode();

               string retMsg = ExtTrade.ResultComment();

               if(retCode == 10025 || StringFind(retMsg, "No changes") >= 0 || StringFind(retMsg, "no changes") >= 0)

               {

                  ExtLastActionMsg = StringFormat("Posicion #%I64u ya blindada (SL: %.*f)", ticket, digits, newSl);

                  PrintFormat("[EA MT5] [AL DIA] Posicion #%I64u sin cambios requeridos (SL ya en %.*f). Confirmando a la nube.", 

                              ticket, digits, newSl);

                  ConfirmActionToCloud(actionId, ticket, newSl, true);

               }

               else

               {

                  PrintFormat("[EA MT5] [AVISO] Fallo al modificar SL: %s (Codigo: %u)", retMsg, retCode);

               }

            }

            break;

         }

      }

      if(!found)

      {

         PrintFormat("[EA MT5] [AVISO] No se encontro posicion abierta con Magic %I64u para MODIFY_SL. Confirmando accion #%d para liberar cola.", 

                     InpMagicNumber, actionId);

         ConfirmActionToCloud(actionId, 0, 0.0, true);

      }

   }

   

   // D. CIERRE FORZOSO O DE FIN DE SEMANA (CLOSE)

   else if(action == "CLOSE_POSITION" || action == "CLOSE_ALL")

   {

      bool found = false;

      for(int i = PositionsTotal() - 1; i >= 0; i--)

      {

         ulong ticket = PositionGetTicket(i);

         if(ticket > 0 && PositionGetInteger(POSITION_MAGIC) == InpMagicNumber)

         {

            if(action == "CLOSE_POSITION" && PositionGetString(POSITION_SYMBOL) != realSymbol)

            {

               continue; // Omitir posicion de otro activo diferente al solicitado

            }

            found = true;

            PrintFormat("[EA MT5] Cerrando posicion #%I64u a precio de mercado...", ticket);

            bool closedSuccess = false;

            ENUM_ORDER_TYPE_FILLING fillModes[] = {ORDER_FILLING_IOC, ORDER_FILLING_FOK, ORDER_FILLING_RETURN};

            for(int f = 0; f < ArraySize(fillModes); f++)

            {

               ExtTrade.SetTypeFilling(fillModes[f]);

               if(ExtTrade.PositionClose(ticket, (ulong)InpDeviationPoints))

               {

                  closedSuccess = true;

                  break;

               }

            }



            if(closedSuccess)

            {

               ExtLastActionMsg = StringFormat("Posicion #%I64u cerrada a mercado.", ticket);

               PrintFormat("[EA MT5] [EXITO] Posicion #%I64u cerrada correctamente.", ticket);

               ConfirmActionToCloud(actionId, ticket, 0.0, true);

            }

            else

            {

               PrintFormat("[EA MT5] [FALLO] Error al cerrar posicion #%I64u: %s", ticket, ExtTrade.ResultComment());

               ConfirmActionToCloud(actionId, ticket, 0.0, false);

            }

            break;

         }

      }

      if(!found)

      {

         PrintFormat("[EA MT5] [AVISO] No se encontro posicion abierta para cerrar (Magic %I64u). Confirmando accion #%d a la nube.", 

                     InpMagicNumber, actionId);

         ConfirmActionToCloud(actionId, 0, 0.0, true);

      }

   }

}



//+------------------------------------------------------------------+

//| Expert initialization function                                   |

//+------------------------------------------------------------------+

int OnInit()

{

   Print("==================================================================");

   Print("  INICIANDO EXPERT ADVISOR: STELLARLITE WEBHOOK BRIDGE (MT5)     ");

   Print("  Modelo: FundedNext Stellar Lite ($10,000) | NY_OPEN (Oro)        ");

   Print("==================================================================");



   ExtTrade.SetExpertMagicNumber(InpMagicNumber);

   ExtTrade.SetDeviationInPoints(InpDeviationPoints);

   ExtTrade.SetTypeFillingBySymbol(ResolveBrokerSymbol(InpPreferredSymbol));



   // Asegurar que los simbolos del portafolio esten visibles en Market Watch

   SymbolSelect("XAUUSD", true);

   SymbolSelect("EURUSD", true);

   SymbolSelect("USDJPY", true);

   SymbolSelect("AUDUSD", true);

   if(InpEnableSP500) SymbolSelect("US500", true);



   // Comprobacion inicial de conectividad con Oracle Cloud

   string resp;

   int status;

   string healthUrl = InpServerUrl + "/api/health";

   

   if(SendHttpRequest("GET", healthUrl, "", resp, status))

   {

      ExtServerStatus = "CONECTADO A ORACLE CLOUD (ONLINE)";

      PrintFormat("[EA MT5] Conectado exitosamente con servidor Webhook: %s", resp);

   }

   else

   {

      ExtServerStatus = "CONECTANDO... (Revisa que la URL este autorizada en MT5)";

   }



   EventSetTimer(InpPollIntervalSec);

   UpdateChartDashboard();

   return(INIT_SUCCEEDED);

}



//+------------------------------------------------------------------+

//| Expert deinitialization function                                 |

//+------------------------------------------------------------------+

void OnDeinit(const int reason)

{

   EventKillTimer();

   Comment("");

   Print("[EA MT5] Expert Advisor desinstalado del grafico.");

}



void CheckAutonomousStructuralTrailing()

{

   for(int i = PositionsTotal() - 1; i >= 0; i--)

   {

      ulong ticket = PositionGetTicket(i);

      if(ticket > 0 && PositionGetInteger(POSITION_MAGIC) == InpMagicNumber)

      {

         string sym = PositionGetString(POSITION_SYMBOL);

         ENUM_POSITION_TYPE pType = (ENUM_POSITION_TYPE)PositionGetInteger(POSITION_TYPE);

         double openPrice = PositionGetDouble(POSITION_PRICE_OPEN);

         double curSl = PositionGetDouble(POSITION_SL);

         double curTp = PositionGetDouble(POSITION_TP);

         int digits = (int)SymbolInfoInteger(sym, SYMBOL_DIGITS);

         double pt = SymbolInfoDouble(sym, SYMBOL_POINT);



         MqlTick tick;

         if(!SymbolInfoTick(sym, tick)) continue;



         // Obtener distancia invariante de 1R desde el Take Profit (R:R 1:2.0) o desde el SL inicial

         double initialRiskDist = 0.0;

         if(curTp > 0.0 && MathAbs(curTp - openPrice) > (10 * pt))

         {

            initialRiskDist = MathAbs(curTp - openPrice) / 2.0;

         }

         else if(curSl > 0.0 && ((pType == POSITION_TYPE_BUY && curSl < openPrice) || (pType == POSITION_TYPE_SELL && curSl > openPrice)))

         {

            initialRiskDist = MathAbs(openPrice - curSl);

         }

         else

         {

            if(digits >= 4) initialRiskDist = 200 * pt;

            else if(openPrice > 1000) initialRiskDist = (StringFind(sym, "XAU") >= 0 || StringFind(sym, "GOLD") >= 0) ? 15.0 : 25.0;

            else initialRiskDist = 50 * pt;

         }



         if(initialRiskDist <= (5 * pt)) continue;



         double beTriggerR, beOffset, lock1TriggerR, lock1GainR, lock2TriggerR, lock2GainR, trailTriggerR, trailBufferR, stagnationRangeR, minTightBuffer;

         int trailBarsM15;

         GetAssetTrailingProfile(

            sym, digits, pt, initialRiskDist,

            beTriggerR, beOffset, lock1TriggerR, lock1GainR, lock2TriggerR, lock2GainR,

            trailTriggerR, trailBarsM15, trailBufferR, stagnationRangeR, minTightBuffer

         );



         double gainDist = (pType == POSITION_TYPE_BUY) ? (tick.bid - openPrice) : (openPrice - tick.ask);

         double currentR = gainDist / initialRiskDist;



         // Memoria Persistente de Nivel 3/4: si el SL actual ya aseguro >= lock2GainR (+1.10R), el Trailing M15 permanece activo

         double lockedDist = 0.0;

         if(curSl > 0.0)

         {

            lockedDist = (pType == POSITION_TYPE_BUY) ? (curSl - openPrice) : (openPrice - curSl);

         }

         double lockedR = lockedDist / initialRiskDist;

         bool isLatchedLevel3 = (lockedR >= (lock2GainR - 0.02));



         if(currentR < beTriggerR && !isLatchedLevel3) continue;



         // Detectar ventana Pre-Rollover Bancario (23:30 a 23:59 hora servidor MT5 = 16:30 a 16:59 EST)

         MqlDateTime dtSrv;

         TimeCurrent(dtSrv);

         bool isPreRollover = (dtSrv.hour == 23 && dtSrv.min >= 30);



         long stopLvlPts = SymbolInfoInteger(sym, SYMBOL_TRADE_STOPS_LEVEL);

         double minSafeDist = MathMax((double)stopLvlPts * pt, 10.0 * pt);



         if(pType == POSITION_TYPE_BUY)

         {

            double targetSl = 0.0;

            string stepTag = "";



            // Nivel 1: Break-Even+ (Cobertura de Comision/Spread)

            if(currentR >= beTriggerR)

            {

               targetSl = openPrice + beOffset;

               stepTag = StringFormat("Nivel 1 BE+ (+%.2fR alcanzado)", beTriggerR);

            }

            // Nivel 2: Primer Candado de Ganancia

            if(currentR >= lock1TriggerR)

            {

               targetSl = openPrice + (initialRiskDist * lock1GainR);

               stepTag = StringFormat("Nivel 2 Candado +%.2fR (+%.2fR alcanzado)", lock1GainR, lock1TriggerR);

            }

            // Nivel 3: Segundo Candado cercano a TP

            if(currentR >= lock2TriggerR)

            {

               targetSl = openPrice + (initialRiskDist * lock2GainR);

               stepTag = StringFormat("Nivel 3 Candado +%.2fR (+%.2fR alcanzado)", lock2GainR, lock2TriggerR);

            }



            // Nivel 4: Trailing Estructural M15 con Memoria Persistente + Detector de Estancamiento / Pre-Rollover

            if(currentR >= trailTriggerR || isLatchedLevel3)

            {

               MqlRates ratesM15[];

               ArraySetAsSeries(ratesM15, true);

               int copied = CopyRates(sym, PERIOD_M15, 1, 3, ratesM15);

               if(copied >= trailBarsM15)

               {

                  double maxHigh3 = ratesM15[0].high;

                  double minLow3  = ratesM15[0].low;

                  for(int c = 1; c < copied; c++)

                  {

                     if(ratesM15[c].high > maxHigh3) maxHigh3 = ratesM15[c].high;

                     if(ratesM15[c].low < minLow3)   minLow3  = ratesM15[c].low;

                  }

                  bool isStagnant = ((maxHigh3 - minLow3) <= (initialRiskDist * stagnationRangeR));

                  int usedBars = (isStagnant || isPreRollover) ? 1 : trailBarsM15;



                  double minLow = ratesM15[0].low;

                  for(int k = 1; k < usedBars; k++)

                  {

                     if(ratesM15[k].low < minLow) minLow = ratesM15[k].low;

                  }

                  double buffer = (isStagnant || isPreRollover)

                                  ? MathMax(minTightBuffer, initialRiskDist * 0.05)

                                  : MathMax(5.0 * pt, initialRiskDist * trailBufferR);

                  double structSl = minLow - buffer;

                  if(structSl > (openPrice + beOffset) && structSl > targetSl && structSl <= (tick.bid - minSafeDist))

                  {

                     targetSl = structSl;

                     if(isPreRollover)

                        stepTag = "Escudo Pre-Rollover M15 (1 vela)";

                     else if(isStagnant)

                        stepTag = "Trailing Anti-Estancamiento M15 (1 vela)";

                     else

                        stepTag = StringFormat("Trailing Estructural M15 (%d velas)", usedBars);

                  }

               }

            }



            targetSl = NormalizeDouble(targetSl, digits);

            if(targetSl > 0.0 && (curSl == 0.0 || targetSl > (curSl + (2.0 * pt))) && targetSl <= (tick.bid - minSafeDist))

            {

               PrintFormat("[EA MT5] [ESCALERA SL] BUY #%I64u (%s) -> %s | Nuevo SL: %.*f (Anterior: %.*f)",

                           ticket, sym, stepTag, digits, targetSl, digits, curSl);

               if(ExtTrade.PositionModify(ticket, targetSl, curTp))

               {

                  ExtLastActionMsg = StringFormat("BUY #%I64u %s @ %.*f", ticket, stepTag, digits, targetSl);

               }

            }

         }

         else if(pType == POSITION_TYPE_SELL)

         {

            double targetSl = 0.0;

            string stepTag = "";



            // Nivel 1: Break-Even+ (Cobertura de Comision/Spread)

            if(currentR >= beTriggerR)

            {

               targetSl = openPrice - beOffset;

               stepTag = StringFormat("Nivel 1 BE+ (+%.2fR alcanzado)", beTriggerR);

            }

            // Nivel 2: Primer Candado de Ganancia

            if(currentR >= lock1TriggerR)

            {

               targetSl = openPrice - (initialRiskDist * lock1GainR);

               stepTag = StringFormat("Nivel 2 Candado +%.2fR (+%.2fR alcanzado)", lock1GainR, lock1TriggerR);

            }

            // Nivel 3: Segundo Candado cercano a TP

            if(currentR >= lock2TriggerR)

            {

               targetSl = openPrice - (initialRiskDist * lock2GainR);

               stepTag = StringFormat("Nivel 3 Candado +%.2fR (+%.2fR alcanzado)", lock2GainR, lock2TriggerR);

            }



            // Nivel 4: Trailing Estructural M15 con Memoria Persistente + Detector de Estancamiento / Pre-Rollover

            if(currentR >= trailTriggerR || isLatchedLevel3)

            {

               MqlRates ratesM15[];

               ArraySetAsSeries(ratesM15, true);

               int copied = CopyRates(sym, PERIOD_M15, 1, 3, ratesM15);

               if(copied >= trailBarsM15)

               {

                  double maxHigh3 = ratesM15[0].high;

                  double minLow3  = ratesM15[0].low;

                  for(int c = 1; c < copied; c++)

                  {

                     if(ratesM15[c].high > maxHigh3) maxHigh3 = ratesM15[c].high;

                     if(ratesM15[c].low < minLow3)   minLow3  = ratesM15[c].low;

                  }

                  bool isStagnant = ((maxHigh3 - minLow3) <= (initialRiskDist * stagnationRangeR));

                  int usedBars = (isStagnant || isPreRollover) ? 1 : trailBarsM15;



                  double maxHigh = ratesM15[0].high;

                  for(int k = 1; k < usedBars; k++)

                  {

                     if(ratesM15[k].high > maxHigh) maxHigh = ratesM15[k].high;

                  }

                  double buffer = (isStagnant || isPreRollover)

                                  ? MathMax(minTightBuffer, initialRiskDist * 0.05)

                                  : MathMax(5.0 * pt, initialRiskDist * trailBufferR);

                  double structSl = maxHigh + buffer;

                  if(structSl < (openPrice - beOffset) && (targetSl == 0.0 || structSl < targetSl) && structSl >= (tick.ask + minSafeDist))

                  {

                     targetSl = structSl;

                     if(isPreRollover)

                        stepTag = "Escudo Pre-Rollover M15 (1 vela)";

                     else if(isStagnant)

                        stepTag = "Trailing Anti-Estancamiento M15 (1 vela)";

                     else

                        stepTag = StringFormat("Trailing Estructural M15 (%d velas)", usedBars);

                  }

               }

            }



            targetSl = NormalizeDouble(targetSl, digits);

            if(targetSl > 0.0 && (curSl == 0.0 || targetSl < (curSl - (2.0 * pt))) && targetSl >= (tick.ask + minSafeDist))

            {

               PrintFormat("[EA MT5] [ESCALERA SL] SELL #%I64u (%s) -> %s | Nuevo SL: %.*f (Anterior: %.*f)",

                           ticket, sym, stepTag, digits, targetSl, digits, curSl);

               if(ExtTrade.PositionModify(ticket, targetSl, curTp))

               {

                  ExtLastActionMsg = StringFormat("SELL #%I64u %s @ %.*f", ticket, stepTag, digits, targetSl);

               }

            }

         }

      }

   }

}



//+------------------------------------------------------------------+

//| Expert timer function (Polling continuo al Servidor Webhook)     |

//+------------------------------------------------------------------+

void OnTimer()

{

   ExtLastPollTime = TimeCurrent();



   // Extraer ticks en tiempo real del broker para alimentar el feed de MT5 hacia la nube (Sandbox + Live)

   string symGold = ResolveBrokerSymbol("XAUUSD");

   string symEur  = ResolveBrokerSymbol("EURUSD");

   string symJpy  = ResolveBrokerSymbol("USDJPY");

   string symAud  = ResolveBrokerSymbol("AUDUSD");

   string symSp   = ResolveBrokerSymbol("US500");



   MqlTick tickGold, tickEur, tickJpy, tickAud, tickSp;

   string feedParams = "";

   bool hasGold = (symGold != "INACTIVE" && symGold != "") ? SymbolInfoTick(symGold, tickGold) : false;

   bool hasEur  = (symEur != "INACTIVE" && symEur != "") ? SymbolInfoTick(symEur, tickEur) : false;

   bool hasJpy  = (symJpy != "INACTIVE" && symJpy != "") ? SymbolInfoTick(symJpy, tickJpy) : false;

   bool hasAud  = (symAud != "INACTIVE" && symAud != "") ? SymbolInfoTick(symAud, tickAud) : false;

   bool hasSp   = (symSp != "INACTIVE" && symSp != "") ? SymbolInfoTick(symSp, tickSp) : false;



   if(hasGold || hasEur || hasJpy || hasAud || hasSp)

   {

      feedParams = StringFormat(

         "?feed=1&xau_bid=%.2f&xau_ask=%.2f&eur_bid=%.5f&eur_ask=%.5f&jpy_bid=%.3f&jpy_ask=%.3f&aud_bid=%.5f&aud_ask=%.5f&sp_bid=%.2f&sp_ask=%.2f",

         hasGold ? tickGold.bid : 0.0, hasGold ? tickGold.ask : 0.0,

         hasEur ? tickEur.bid : 0.0, hasEur ? tickEur.ask : 0.0,

         hasJpy ? tickJpy.bid : 0.0, hasJpy ? tickJpy.ask : 0.0,

         hasAud ? tickAud.bid : 0.0, hasAud ? tickAud.ask : 0.0,

         hasSp ? tickSp.bid : 0.0, hasSp ? tickSp.ask : 0.0

      );

   }



   string signalUrl = InpServerUrl + "/api/signal" + feedParams;

   string resp;

   int status;

   

   if(SendHttpRequest("GET", signalUrl, "", resp, status))

   {

      ExtConsecutiveErrors = 0;

      ExtServerStatus = "CONECTADO A ORACLE CLOUD (ONLINE)";

      

      bool hasAction = JsonExtractBool(resp, "has_action");

      if(hasAction)

      {

         ExtCloudZeroTradeConsecutiveCycles = 0;

         ProcessCloudAction(resp);

      }

      else

         // Auto-Sincronizaci?n de Seguridad con Filtro Anti-Falso Cierre y Debounce:

         // Requiere:

         // 1. Que la clave 'open_trades_count' exista EXPLICITAMENTE en el JSON del servidor.

         // 2. Que el conteo reportado sea exactamente 0.

         // 3. Que esta confirmaci?n se sostenga por al menos 4 ciclos consecutivos (~20 segundos),

         //    evitando liquidaciones accidentales ante micro-cortes, latencias o respuestas fragmentadas.

         if(JsonHasKey(resp, "open_trades_count"))

         {

            double openTradesCloud = JsonExtractDouble(resp, "open_trades_count");

            if(openTradesCloud == 0.0)

            {

               ExtCloudZeroTradeConsecutiveCycles++;

               if(ExtCloudZeroTradeConsecutiveCycles >= 4)

               {

                  for(int i = PositionsTotal() - 1; i >= 0; i--)

                  {

                     ulong ticket = PositionGetTicket(i);

                     if(ticket > 0 && PositionGetInteger(POSITION_MAGIC) == InpMagicNumber)

                     {

                        datetime posTime = (datetime)PositionGetInteger(POSITION_TIME);

                        if(TimeCurrent() - posTime > 30)

                        {

                           PrintFormat("[EA MT5] [AUTO-SYNC] Cierre confirmado por nube (open_trades_count = 0 sostenido por %d ciclos). Sincronizando posicion #%I64u...", 

                                       ExtCloudZeroTradeConsecutiveCycles, ticket);

                           ENUM_ORDER_TYPE_FILLING fillModes[] = {ORDER_FILLING_IOC, ORDER_FILLING_FOK, ORDER_FILLING_RETURN};

                           bool closedOk = false;

                           for(int f = 0; f < ArraySize(fillModes); f++)

                           {

                              ExtTrade.SetTypeFilling(fillModes[f]);

                              if(ExtTrade.PositionClose(ticket, (ulong)InpDeviationPoints))

                              {

                                 closedOk = true;

                                 break;

                              }

                           }

                           if(closedOk)

                           {

                              ExtLastActionMsg = StringFormat("Posicion #%I64u auto-sincronizada y cerrada.", ticket);

                              PrintFormat("[EA MT5] [AUTO-SYNC] Posicion #%I64u cerrada con exito.", ticket);

                           }

                        }

                     }

                  }

               }

            }

            else

            {

               ExtCloudZeroTradeConsecutiveCycles = 0;

            }

         }

         else

         {

            ExtCloudZeroTradeConsecutiveCycles = 0;

         }

   }

   else

   {

      ExtConsecutiveErrors++;

      if(ExtConsecutiveErrors >= 5)

      {

         ExtServerStatus = StringFormat("FALLO DE CONEXION (%d reintentos fallidos)", ExtConsecutiveErrors);

      }

   }



   // Guardia de blindaje autónomo Break-Even local y Trailing Stop M15

   CheckAutonomousStructuralTrailing();

   

   UpdateChartDashboard();

}



//+------------------------------------------------------------------+

//| Expert tick function                                             |

//+------------------------------------------------------------------+

void OnTick()

{

   // Evaluar en cada tick la escalera de Break-Even+ y Candados de Ganancia

   CheckAutonomousStructuralTrailing();

}

//+------------------------------------------------------------------+

