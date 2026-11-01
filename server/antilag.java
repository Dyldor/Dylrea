// This resets server every 30 mins to stop lag - xerozcheez
import java.io.*;

public class antilag
{

public int ResetTimer = 0;

public void resetserver()
{
misc.println("RESETING SERVER!!!");
misc.println("Saving all games...");
PlayerHandler.kickAllPlayers = true;
misc.println("GAME SUCCESSFULLY SAVED FOR ALL PLAYERS");
ResetTimer = 0;
closeListener();
runserver();
}
public void process()
{
ResetTimer += 1;
if(ResetTimer >= 9999999)
{
resetserver();
}
}

public void runserver()
{
  try 
{
// Auto-restart via external .bat removed: the original script killed every Java process.
misc.println("Server listener closed; restart the server manually.");
if (false) throw new IOException();
} 
catch (IOException ioe) 
{
	 ioe.printStackTrace();
} 
}

public void closeListener()
{
		try {
			server.shutdownClientHandler = true;
			if(server.clientListener != null) server.clientListener.close();
			server.clientListener = null;
		} 
catch(java.lang.Exception __ex) 
{
			__ex.printStackTrace();
}
}
}