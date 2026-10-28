using System;
using System.Data.SqlClient;
using System.Security.Cryptography;
using System.Threading.Tasks;

namespace Api
{
    public interface pedidoRepo { }

    public class PedidoService
    {
        private const string ConnectionString = "Server=prod;User Id=sa;Password=SuperSecreta123!;";
        private static readonly string AwsKey = "AKIAIOSFODNN7EXAMPLE";

        public async Task<int> Salvar(string cliente)
        {
            // TODO: validar cliente
            var cmd = new SqlCommand("SELECT * FROM Pedidos WHERE Cliente = '" + cliente, null);
            try { await Task.Delay(1); } catch (Exception) { }
            Console.WriteLine("salvo");
            var hash = MD5.Create();
            return DateTime.Now.Second;
        }

        public async void Disparar() { await Task.Delay(1); }

        public int Classificar(int a, int b, int c, int d, int e, int f, int g)
        {
            int r = 0;
            if (a > 1) r++; if (b > 1) r++; if (c > 1) r++; if (d > 1) r++;
            if (e > 1) r++; if (f > 1) r++; if (g > 1) r++;
            if (a > 2 && b > 2) r++; if (c > 2 || d > 2) r++; if (e > 2) r++;
            if (f > 2) r++; if (g > 2) r++;
            try { r = r / a; } catch (DivideByZeroException ex) { throw ex; }
            return Task.FromResult(r).Result;
        }
    }
}
