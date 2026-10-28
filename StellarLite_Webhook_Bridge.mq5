//+------------------------------------------------------------------+
//|                                   StellarLite_Webhook_Bridge.mq5 |
//|              FundedNext Stellar Lite ($5,000) - Webhook Bridge EA |
//|          Conecta MetaTrader 5 con el Motor Cuantitativo 24/7 OCI |
//+------------------------------------------------------------------+
#property copyright   "FundedNext Stellar Lite Quantitative Engine"
#property link        "https://github.com/victorsvlynch/ftmo_stellar_lite"
#property version     "2.00"
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

//--- Instancias Globales
CTrade         ExtTrade;
datetime       ExtLastPollTime = 0;
string         ExtServerStatus = "DESCONECTADO";
string         ExtLastActionMsg = "Esperando primera conexion...";
int            ExtConsecutiveErrors = 0;

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
//| Resolver simbolo real del broker para Oro                        |
//+------------------------------------------------------------------+
string ResolveBrokerSymbol(const string requestedSymbol)
{
   if(SymbolInfoDouble(requestedSymbol, SYMBOL_BID) > 0)
      return requestedSymbol;
      
   // Probar variaciones comunes
   string candidates[] = {"XAUUSD", "GOLD", "XAUUSDm", "XAUUSD.raw", "XAUUSD.pro", "XAUUSDb"};
   for(int i = 0; i < ArraySize(candidates); i++)
   {
      if(SymbolInfoDouble(candidates[i], SYMBOL_BID) > 0)
         return candidates[i];
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
   text += "  FUNDEDNEXT STELLAR LITE ($5,000) -- WEBHOOK BRIDGE EA MT5\n";
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
void ProcessCloudAction(const string json)
{
   int actionId = (int)JsonExtractDouble(json, "action_id");
   string action = JsonExtractString(json, "action");
   string symReq = JsonExtractString(json, "symbol");
   double lots = JsonExtractDouble(json, "lots");
   double sl = JsonExtractDouble(json, "sl");
   double tp = JsonExtractDouble(json, "tp");
   int tradeId = (int)JsonExtractDouble(json, "trade_id");
   string comment = JsonExtractString(json, "comment");
   if(StringLen(comment) == 0) comment = "FundedNext NY_ORB";
   
   string realSymbol = ResolveBrokerSymbol(symReq);
   
   // A. APERTURA DE COMPRA (BUY)
   if(action == "OPEN_BUY")
   {
      // Verificar si ya tenemos posicion abierta con ese trade_id o magic
      bool alreadyOpen = false;
      for(int i = PositionsTotal() - 1; i >= 0; i--)
      {
         ulong ticket = PositionGetTicket(i);
         if(ticket > 0 && PositionGetInteger(POSITION_MAGIC) == InpMagicNumber)
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
         double slPrice = (sl > 0 && sl < askPrice) ? NormalizeDouble(sl, digits) : NormalizeDouble(askPrice - 6.50, digits);
         double tpPrice = (tp > 0 && tp > askPrice) ? NormalizeDouble(tp, digits) : NormalizeDouble(askPrice + 13.00, digits);

         PrintFormat("[EA MT5] Ejecutando COMPRA institucional: %s %.2f lotes @ %.2f | SL: %.2f | TP: %.2f", realSymbol, lots, askPrice, slPrice, tpPrice);

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
         if(ticket > 0 && PositionGetInteger(POSITION_MAGIC) == InpMagicNumber)
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
         double slPrice = (sl > 0 && sl > bidPrice) ? NormalizeDouble(sl, digits) : NormalizeDouble(bidPrice + 6.50, digits);
         double tpPrice = (tp > 0 && tp < bidPrice) ? NormalizeDouble(tp, digits) : NormalizeDouble(bidPrice - 13.00, digits);

         PrintFormat("[EA MT5] Ejecutando VENTA institucional: %s %.2f lotes @ %.2f | SL: %.2f | TP: %.2f", realSymbol, lots, bidPrice, slPrice, tpPrice);

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
   
   // C. MODIFICACION DE STOP LOSS A BREAK-EVEN
   else if(action == "MODIFY_SL")
   {
      for(int i = PositionsTotal() - 1; i >= 0; i--)
      {
         ulong ticket = PositionGetTicket(i);
         if(ticket > 0 && PositionGetInteger(POSITION_MAGIC) == InpMagicNumber)
         {
            double curTp = PositionGetDouble(POSITION_TP);
            PrintFormat("[EA MT5] Blindando posicion #%I64u con Break-Even: Nuevo SL: %.2f", ticket, sl);
            if(ExtTrade.PositionModify(ticket, sl, curTp))
            {
               ExtLastActionMsg = StringFormat("Posicion #%I64u blindada a Break-Even (SL: %.2f)", ticket, sl);
               PrintFormat("[EA MT5] [EXITO] Posicion #%I64u modificada a Break-Even.", ticket);
               ConfirmActionToCloud(actionId, ticket, sl, true);
            }
            else
            {
               PrintFormat("[EA MT5] [AVISO] Fallo al modificar SL a Break-Even: %s", ExtTrade.ResultComment());
            }
            break;
         }
      }
   }
   
   // D. CIERRE FORZOSO O DE FIN DE SEMANA (CLOSE)
   else if(action == "CLOSE_POSITION" || action == "CLOSE_ALL")
   {
      for(int i = PositionsTotal() - 1; i >= 0; i--)
      {
         ulong ticket = PositionGetTicket(i);
         if(ticket > 0 && PositionGetInteger(POSITION_MAGIC) == InpMagicNumber)
         {
            PrintFormat("[EA MT5] Cerrando posicion #%I64u a precio de mercado...", ticket);
            if(ExtTrade.PositionClose(ticket, (ulong)InpDeviationPoints))
            {
               ExtLastActionMsg = StringFormat("Posicion #%I64u cerrada a mercado.", ticket);
               PrintFormat("[EA MT5] [EXITO] Posicion #%I64u cerrada correctamente.", ticket);
               ConfirmActionToCloud(actionId, ticket, 0.0, true);
            }
            break;
         }
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
   Print("  Modelo: FundedNext Stellar Lite ($5,000) | NY_OPEN (Oro)        ");
   Print("==================================================================");

   ExtTrade.SetExpertMagicNumber(InpMagicNumber);
   ExtTrade.SetDeviationInPoints(InpDeviationPoints);
   ExtTrade.SetTypeFillingBySymbol(ResolveBrokerSymbol(InpPreferredSymbol));

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

//+------------------------------------------------------------------+
//| Expert timer function (Polling continuo al Servidor Webhook)     |
//+------------------------------------------------------------------+
void OnTimer()
{
   ExtLastPollTime = TimeCurrent();
   string signalUrl = InpServerUrl + "/api/signal";
   string resp;
   int status;
   
   if(SendHttpRequest("GET", signalUrl, "", resp, status))
   {
      ExtConsecutiveErrors = 0;
      ExtServerStatus = "CONECTADO A ORACLE CLOUD (ONLINE)";
      
      bool hasAction = JsonExtractBool(resp, "has_action");
      if(hasAction)
      {
         ProcessCloudAction(resp);
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
   
   UpdateChartDashboard();
}

//+------------------------------------------------------------------+
//| Expert tick function                                             |
//+------------------------------------------------------------------+
void OnTick()
{
   // El sondeo principal se ejecuta en OnTimer para no sobrecargar el servidor
}
//+------------------------------------------------------------------+
