import java.awt.BorderLayout;
import java.awt.Font;
import java.io.File;
import java.net.InetSocketAddress;
import java.net.Socket;
import javax.swing.BorderFactory;
import javax.swing.JFrame;
import javax.swing.JLabel;
import javax.swing.JOptionPane;
import javax.swing.SwingUtilities;

/**
 * RetroRemakeRSPS one-click launcher.
 * Starts the game server (unless one is already running on port 43594), waits for it, opens the client,
 * and stops the server again a little while after the client is closed (so your character is saved).
 */
public class Launcher {
	private static final int PORT = 43594;
	private static JFrame window;
	private static JLabel status;

	public static void main(String[] args) {
		try {
			run();
		} catch (Throwable t) {
			fail("RetroRemakeRSPS could not start:\n" + t);
		}
	}

	private static void run() throws Exception {
		File home = new File(Launcher.class.getProtectionDomain().getCodeSource().getLocation().toURI()).getParentFile();
		File serverDir = new File(home, "server"), clientDir = new File(home, "client");
		File serverJar = new File(home, "lib/server.jar"), clientJar = new File(home, "lib/client.jar");
		if (!serverJar.exists() || !clientJar.exists() || !serverDir.isDirectory() || !clientDir.isDirectory()) {
			fail("Keep RetroRemakeRSPS.jar inside the RetroRemakeRSPS folder\n(next to the lib, server and client folders).\n\nLooked in: " + home);
			return;
		}
		String java = System.getProperty("java.home") + File.separator + "bin" + File.separator + "java";
		show("Starting the RetroRemakeRSPS server...");
		Process server = null;
		if (!portOpen()) {
			new File(serverDir, "logs").mkdirs();
			new File(serverDir, "characters").mkdirs();
			ProcessBuilder pb = new ProcessBuilder(java, "-Xmx768m", "-cp", serverJar.getAbsolutePath(), "server");
			pb.directory(serverDir);
			pb.redirectErrorStream(true);
			pb.redirectOutput(new File(serverDir, "logs/server-console.log"));
			server = pb.start();
			final Process s = server;
			Runtime.getRuntime().addShutdownHook(new Thread() { public void run() { s.destroy(); } });
			long deadline = System.currentTimeMillis() + 90000;
			while (!portOpen()) {
				if (!isAlive(server)) {
					fail("The server stopped while starting.\nSee server/logs/server-console.log for details.");
					return;
				}
				if (System.currentTimeMillis() > deadline) {
					fail("The server did not start within 90 seconds.\nSee server/logs/server-console.log for details.");
					return;
				}
				Thread.sleep(500);
			}
		}
		if (server != null) {
			Thread.sleep(3000);    // the port opens before the game loop; make sure the server survived start-up
			if (!isAlive(server)) {
				fail("The server stopped while starting.\nSee server/logs/server-console.log for details.");
				return;
			}
		}
		show("Opening the game...");
		ProcessBuilder pc = new ProcessBuilder(java, "-Xmx512m", "-cp", clientJar.getAbsolutePath(), "EGUI");
		pc.directory(clientDir);
		pc.redirectErrorStream(true);
		pc.redirectOutput(new File(clientDir, "client-console.log"));
		Process client = pc.start();
		Thread.sleep(3000);
		hide();
		client.waitFor();
		if (server != null) {
			show("Saving and stopping the server...");
			Thread.sleep(20000);     // let the logout and save finish
			server.destroy();
		}
		System.exit(0);
	}

	private static boolean isAlive(Process p) {
		try { p.exitValue(); return false; } catch (IllegalThreadStateException e) { return true; }
	}

	private static boolean portOpen() {
		Socket s = new Socket();
		try {
			s.connect(new InetSocketAddress("127.0.0.1", PORT), 300);
			return true;
		} catch (Exception e) {
			return false;
		} finally {
			try { s.close(); } catch (Exception ignored) { }
		}
	}

	private static void show(final String text) {
		try {
			SwingUtilities.invokeAndWait(new Runnable() { public void run() {
				if (window == null) {
					window = new JFrame("RetroRemakeRSPS");
					status = new JLabel(text);
					status.setFont(status.getFont().deriveFont(Font.BOLD, 14f));
					status.setBorder(BorderFactory.createEmptyBorder(24, 32, 24, 32));
					window.getContentPane().add(status, BorderLayout.CENTER);
					window.setDefaultCloseOperation(JFrame.DO_NOTHING_ON_CLOSE);
					window.pack();
					window.setLocationRelativeTo(null);
				}
				status.setText(text);
				window.pack();
				window.setVisible(true);
			} });
		} catch (Exception headless) {
			System.out.println(text);
		}
	}

	private static void hide() {
		if (window != null) SwingUtilities.invokeLater(new Runnable() { public void run() { window.setVisible(false); } });
	}

	private static void fail(String msg) {
		hide();
		try {
			JOptionPane.showMessageDialog(null, msg, "RetroRemakeRSPS", JOptionPane.ERROR_MESSAGE);
		} catch (Throwable headless) {
			System.err.println(msg);
		}
		System.exit(1);
	}
}
